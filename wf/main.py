from wf.DSI_Studio_base import *
from wf.utils import (patient_scan, read_config, split_chpid, find_best,
						join_strs, add_id_subs)
from nipype import IdentityInterface, SelectFiles, Function
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
from nipype.interfaces import fsl
from nipype.interfaces.utility import Rename, Select, Split
from nipype.workflows.dmri.fsl import tbss


#anacfgpath = '/home/pirc/Desktop/DWI/DINGO/res/Neonates_analysis_config.json'#os.environ["ana_config"]
#anacfg = read_config(anacfgpath)


##Check for included sub/scan list
#if "included_psids" in anacfg:
	#scanlist = anacfg["included_psids"]
	#t_scanlist = frozenset(scanlist)
#else:
	#raise KeyError("included_psids not identified in analysis config")

#for root,dirs,files in os.walk(anacfg["data_dir"]):#parent to subject files
#	for f in files:
#		if re.search('config\.json(?!~)',f): #ignore old versions
#			potential = read_config(os.path.abspath(os.path.join(root,f)))
#			try:
#				pot_id = patient_scan(potential,addSequence=True)
#				t_pot_id = frozenset([pot_id])
#				if bool(t_scanlist.intersection(t_pot_id)):
#					print("%s: INCLUDED" % (pot_id))
#					subcfg = potential
#				else:
#					print("%s: SKIPPED - does not match inclusion list" % 
#						 (pot_id))
#			except KeyError:#not a subject config file
#				pass


def create_split_ids(name="split_ids",sep=None,parent_dir=None,scan_list=None):
	"""Nipype node to iterate a list of CHP ids into separate subject, scan, and
		task ids.
		
		Parameters
		----------
		name		:	Str (workflow name, default 'split_ids')
		sep			:	Str (separator for fields in id, default '_')
		parent_dir	:	Directory (contains subject folders)
		scan_list	:	List[Str] 
			
		e.g. split_ids = create_split_ids(name='split_ids', 
					parent_dir=os.getcwd(),
					scan_list=[0004_MR1_DTIFIXED,CHD_003_02a_DTIFIXED],
					sep='_')
			
		Returns
		-------
		splitids	:	Nipype workflow
		(splitids.outputnode.outputs=['parent_dir','sub_id','scan_id','uid'])
		e.g. {0: {parent_dir='/home/pirc/Desktop/DWI/CHD_tractography/CHP',
					sub_id='0004', scan_id='MR1', uid='DTIFIXED'},
			  1: {parent_dir='/home/pirc/Desktop/DWI/CHD_tractography/CHP',
					sub_id='CHD_003', scan_id='02a', uid='DTIFIXED'}}
	"""
	inputnode = pe.Node(
		name="inputnode",
		interface=IdentityInterface(
			fields=["scan_list"],
			mandatory_inputs=True))
	if scan_list is not None:
		inputnode.inputs.scan_list = scan_list
		inputnode.iterables = ("scan_list", inputnode.inputs.scan_list)
	else:
		print("%s.inputnode.scan_list must be set before running" % name)
			
	splitidsnode = pe.Node(
		name="splitidsnode",
		interface=Function(
			input_names=["psid","sep"],
			output_names=["sub_id","scan_id","uid"],
			function=split_chpid))
	if sep is not None:
		splitidsnode.inputs.sep = sep
	else:
		splitidsnode.inputs.sep = "_"
		
	outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(
			fields=["sub_id",
					"scan_id",
					"uid"],
			mandatory_inputs=True))
			
	#Create Workflow
	splitids = pe.Workflow(name=name)
	splitids.connect([
		(inputnode, splitidsnode, 
			[("scan_list", "psid")]),
		(splitidsnode, outputnode, 
			[("sub_id", "sub_id"),
			("scan_id", "scan_id"),
			("uid", "uid")])
		])
	return splitids

#depending how I want to hook this up, iterate over separate synced id lists
def create_iterate_ids(name="iterate_ids",parent_dir=None, sub_id_list=None, 
scan_id_list=None, uid_list=None):
	"""iterate over synced id lists, separated into sub, scan, uid, with a 
	parent_dir"""
	
	inputnode = pe.Node(
		name="inputnode",
		interface=IdentityInterface(
			fields=[
				"parent_dir",
				"sub_id_list",
				"scan_id_list",
				"uid_list"],
			mandatory_inputs=True))
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
	if sub_id is not None:
		inputnode.inputs.sub_id_list = sub_id_list
	if scan_id is not None:
		inputnode.inputs.scan_id_list = scan_id_list
	if uid is not None:
		inputnode.inputs.uid_list = uid_list
	
	inputnode.iterables = [
		("sub_id_list", inputnode.inputs.sub_id_list),
		("scan_id_list", inputnode.inputs.scan_id_list),
		("uid_list", inputnode.inputs.uid_list)]
	inputnode.synchronize = True
	
	outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(
			fields=[
				"parent_dir",
				"sub_id",
				"scan_id",
				"uid"],
			mandatory_inputs=True))
	
	iteratewf = pe.Workflow(name=name)
	iteratewf.connect([
		(inputnode, outputnode, 
			[("parent_dir", "parent_dir"),
			("sub_id_list","sub_id")
			("scan_id_list","scan_id")
			("uid_list","uid")])
		])
	return iteratewf


def create_genFA(name="genFA",parent_dir=None,sub_id=None,scan_id=None,uid=None,
grabFiles=False):
	"""
	Inputs
	------
	inputnode.parent_dir
	inputnode.sub_id
	inputnode.scan_id
	inputnode.uid
	
	Outputs
	-------
	outputnode.eddyc_file
	outputnode.mask_file
	outputnode.FA_file
	outputnode.V1_file
	
	"""
	
	###Pre-Processing###
	inputnode = pe.Node(
		name="inputnode",
		interface=IdentityInterface(
			fields=[
				"parent_dir",
				"sub_id",
				"scan_id",
				"uid"],
			mandatory_inputs=True))
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
	else:
		inputnode.inputs.parent_dir = os.getcwd()
	if sub_id is not None:
		inputnode.inputs.sub_id = sub_id
	if scan_id is not None:
		inputnode.inputs.scan_id = scan_id
	if uid is not None:
		inputnode.inputs.uid = uid
		
	genFA = pe.Workflow(name=name)
		#base_dir='%s/%s/%s/%s' % 
			#(parent_dir,name,inputnode.inputs.sub_id,inputnode.inputs.scan_id))
	
	#Create Reorient2Std node
	reorient = pe.Node(
		name="reorient",
		interface=fsl.Reorient2Std())
	#reorient.inputs.in_file = datain.outputs.dwi
	
	#Create EddyCorrect node
	eddyc = pe.Node(
		name="eddyc",
		interface=fsl.EddyCorrect())
	eddyc.inputs.ref_num = 0 #b0 volume is first volume
	eddyc.inputs.ignore_exception = True #.nii.gz may be 4 bytes short
	#eddyc.inputs.in_file = reorient.outputs.out_file
	
	#Create Robust BET node
	rbet = pe.Node(
		name="rbet",
		interface=fsl.BET())
	rbet.inputs.robust = True
	rbet.inputs.mask = True
	#rbet.inputs.in_file = eddyc.outputs.out_file
	
	#Create DTIFit node
	dtibasename = pe.Node(
		name='dtibasename',
		interface=Function(
			#arg0=sub_id, arg1=scan_id, arg2=uid
			input_names=['sep','arg0','arg1','arg2'],
			output_names=['string'],
			function=join_strs))
	dtibasename.inputs.sep='_'
	
	dti = pe.Node(
		name="dti",
		interface=fsl.DTIFit())
	#dti.inputs.base_name = join_strs(sep='_',arg0=sub_id,arg1=scan_id,arg2=uid)
	#dti.inputs.bvals = datain.outputs.bvals
	#dti.inputs.bvecs = datain.outputs.bvecs
	#dti.inputs.dwi = eddyc.outputs.out_file
	#dti.inputs.mask = rbet.outputs.mask_file
	
	if grabFiles:
		#DataGrabber - get dwi,bval,bvec
		datain = pe.Node(
			name="datain",
			interface=nio.DataGrabber(
				infields=[
					'sub_id',
					'scan_id',
					'uid'],
				outfields=[
					'dwi',
					'bval',
					'bvec']))
		#datain.inputs.base_directory = inputnode.parent_dir
		#template = subid/scanid/subid_scanid_uid.nii.gz
		datain.inputs.template = "%s/%s/%s_%s_%s.nii.gz"
		datain.inputs.field_template = dict(
			dwi="%s/%s/%s_%s_%s.nii.gz",
			bval="%s/%s/%s_%s_%s.bval",
			bvec="%s/%s/%s_%s_%s.bvec")
		datain.inputs.template_args = dict(
			dwi=[['sub_id','scan_id','sub_id','scan_id','uid']],
			bval=[['sub_id','scan_id','sub_id','scan_id','uid']],
			bvec=[['sub_id','scan_id','sub_id','scan_id','uid']])
		datain.inputs.sort_filelist=True
		
		#Connect datain node
		genFA.connect([
			(inputnode, datain, [('parent_dir','base_directory'),
								('sub_id','sub_id'),
								('scan_id','scan_id'),
								('uid','uid')]),
			(datain, reorient, [("dwi","in_file")]),
			(datain, dti, [("bval", "bvals")]),
			(datain, dti, [("bvec", "bvecs")])
			])
	else:
		print('%s.reorient.inputs.in_file, %s.dti.inputs.in_file, '
			'%s.dti.inputs.bvals, %s.dti.inputs.bvecs must all be connected' % 
			(name, name, name, name))
	
	outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(
			fields=[
				"eddyc_file",
				"FA_file",
				"V1_file",
				"mask_file"],
			mandatory_inputs=True))
	#outputnode.eddyc_file = eddyc.outputs.eddy_corrected
	#outputnode.FA_file = dti.outputs.FA
	#outputnode.V1_file = dti.output.V1
	#outputnode.mask_file = rbet.outputs.mask_file
	
	#Preprocess workflow
	genFA.connect([
		(inputnode, dtibasename, 
			[('sub_id','arg0'),
			('scan_id','arg1'),
			('uid','arg2')]),
		(dtibasename, dti, [('string','base_name')]),
		(reorient, eddyc, [("out_file","in_file")]),
		(eddyc, rbet, [("eddy_corrected","in_file")]),
		(eddyc, dti, [("eddy_corrected","dwi")]),
		(rbet, dti, [("mask_file","mask")]),
		(eddyc, outputnode, [('eddy_corrected','eddyc_file')]),
		(rbet, outputnode, [('mask_file','mask_file')]),
		(dti, outputnode, 
			[("FA", "FA_file"),
			('V1','V1_file')])
		#(joindti, outputnode, 
			#[('FA_list','FA_list'),
			#('V1_list','V1_list')]),
		#(joinmasks, outputnode, [("mask_list","mask_list")])
		])
	return genFA


def create_invwarp_all2best(name="invwarp_all2best",fadir=None, outdir=None):
	"""Calculate inverse warps of files"""
	
	invwarpwf = pe.Workflow(name=name)
	
	inputnode = pe.Node(
		name='inputnode',
		interface=IdentityInterface(
			fields=[
				'data_dir',
				'best_id',
				'all_ids'],
			mandatory_inputs=True))
	inputnode.iterables=('all_ids',inputnode.inputs.all_ids)
	if fadir is not None:
		inputnode.inputs.data_dir = fadir
			
	#grab warps from disk
	datainnode = pe.Node(
		name='datainnode',
		interface=nio.DataGrabber(
			infields=[
				'best_id',
				'other_id'],
			outfields=[
				'other2best',
				'other']))
	#datainnode.inputs.base_directory = inputnode.inputs.data_dir
	datainnode.inputs.template = '%s_to_%s_warp.nii.gz'
	datainnode.inputs.sort_filelist = True
	datainnode.inputs.field_template = dict(
		other2best='%s_to_%s_warp.nii.gz',
		other='%s.nii.gz')
	datainnode.inputs.template_args = dict(
		other2best=[['other_id','best_id']],
		other=[['other_id']])
		
	renamenode = pe.Node(
		name='rename',
		interface=Rename(
			format_string='%(best_id)s_to_%(other_id)s.nii.gz'))
			
	invwarpnode = pe.Node(
		name='invwarp',
		interface=fsl.utils.InvWarp())
	invwarpnode.inputs.relative = True #may not need to be set
		
	dataoutnode = pe.Node(
		name='dataoutnode',
		interface=nio.DataSink())
	dataoutnode.inputs.substitutions = [('.nii.gz', '_FINVwarp.nii.gz')]
	if outdir is not None:
		dataoutnode.inputs.base_directory=outdir
	
	outputnode = pe.Node(
		name='outputnode',
		interface=IdentityInterface(
			fields=['invwarp_file'],
			mandatory_inputs=True))
		
	
	invwarpwf.connect([
		(inputnode, datainnode, 
			[('data_dir','base_directory'),
			('best_id','best_id'),
			('all_ids','other_id')]),
		(datainnode, renamenode, 
			[('best_id','best_id'),
			('other_id','other_id')]),
		(datainnode, invwarpnode, 
			[('other2best','warp'),
			('other','reference')]),
		(renamenode, invwarpnode, 
			[('out_file','inverse_warp')]),
		(invwarpnode, dataoutnode, 
			[('inverse_warp','container.scan.@invwarp')]),
		(invwarpnode, outputnode, 
			[('inverse_warp','invwarp_file')])
		])
		
	return invwarpwf

def create_tbss_2_reg_n(name="tbss_2_reg_n", 
parent_dir=None, target=None, id_list=None, fa_list=None, mask_list=None):
	"""TBSS nonlinear registration:
	Performs flirt and fnirt from every file in fa_list to a target
	sub_id, scan_id, uid define target, will result in target warp to itself 
	just like tbss scripts
	
	Inputs
	------
	inputnode.parent_dir
	inputnode.fa_list
	inputnode.mask_list
	inputnode.target
	
	Outputs
	-------
	outputnode.mat_list
	outputnode.fieldcoeff_list
	outputnode.mean_median_list
	"""
	tbss2n = pe.Workflow(name=name)
	
	inputnode = pe.Node(
		name="inputnode",
		interface=IdentityInterface(
			fields=[
				"parent_dir",
				"id_list",
				"fa_list",
				"mask_list",
				"target",
				"target_id"]))
	
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
		#tbss2n.base_dir = parent_dir
	else:
		inputnode.inputs.parent_dir = os.getcwd()
		#tbss2n.base_dir = os.getcwd()
	if target is not None:
		inputnode.inputs.target = target
	if target_id is not None:
		inputnode.inputs.target_id = target_id
	if id_list is not None:
		inputnode.inputs.id_list = id_list
	if fa_list is not None:
		inputnode.inputs.fa_list = fa_list
	if mask_list is not None:
		inputnode.inputs.mask_list = mask_list
		
	i2r = pe.MapNode(
		name='i2r',
		interface=Function(
			#arg0=input_id, arg1=to, arg2=target_id
			input_names=['sep','arg0','arg1','arg2'],
			output_names=['string'],
			function=join_strs),
		iterfield=['arg0'])
	i2r.inputs.sep = '_'
	i2r.inputs.arg1 = 'to'
	
	i2rwarp = pe.MapNode(
		name='i2rwarp',
		interface=Function(
			#arg0=input_to_target, arg1=suffix
			input_names=['sep','arg0','arg1'],
			output_names=['string'],
			function=join_strs),
		iterfield=['arg0'])
	i2rwarp.sep = '_'
	i2rwarp.arg1 = 'warp'
	
	tbss2n.connect([
		(inputnode, i2r, 
			[('id_list','arg0'),
			('target_id','arg2')]),
		(i2r, i2rwarp,
			[('string','arg0')]) ])
			
	#Registration
	flirt = pe.MapNode(
		name="flirt",
		interface=fsl.FLIRT(dof=12),
		iterfield=['in_file','in_weight'])

	fnirt = pe.MapNode(
		name="fnirt",
		interface=fsl.FNIRT(fieldcoeff_file=True),
		iterfield=['in_file', 'affine_file'])
		#values from FA_2_FMRIB58_1mm config copied below, skips flipped
		#ref_file="FMRIB58_FA_1mm"
			#skip_implicit_ref_masking=False,
			#skip_implicit_in_masking=False,
			#refmask_val=0,
			#inmask_val=0,
			#subsampling_scheme=[8,4,2,2],
			#max_nonlin_iter=[5,5,5,5],
			#in_fwhm=[12,6,2,2],
			#ref_fwhm=[12,6,2,2],
			#regularization_lambda=[300,75,30,30],
			#apply_intensity_mapping=[1,1,1,0],
			#warp_resolution=(10,10,10),
			#skip_lambda_ssq=False,
			#regularization_model="bending_energy",
			#intensity_mapping_model="global_linear",
			#derive_from_ref=False),
			
	tbss2n.connect([
		(inputnode, flirt, 
			[("fa_list","in_file"),
			("target","reference"),
			("mask_list","in_weight")]),
		(inputnode, fnirt, 
			[("fa_list","in_file"),
			("target","ref_file")]),
		(i2r, flirt, 
			[('string','out_file')]),
		(i2rwarp, fnirt,
			[('string','fieldcoeff_file')]),
		(flirt, fnirt, 
			[("out_matrix_file", "affine_file")])
		])
			
	if fsl.no_fsl():
		warn('NO FSL found')
	else:
		config_file = os.path.join(os.environ["FSLDIR"],
									"etc/flirtsch/FA_2_FMRIB58_1mm.cnf")
		fnirt.inputs.config_file=config_file

	#Estimate mean & median deformation
	sqrTmean = pe.MapNode(
		name="sqrTmean",
		interface=fsl.ImageMaths(op_string="-sqr -Tmean"),
		iterfield=['in_file'])
	
	meanmedian = pe.MapNode(
		name="meanmedian",
		interface=fsl.ImageStats(op_string="-M -P 50"),
		iterfield=['in_file'])
	
	#if writeFiles:
		##Write files to directories	
		#dataout = pe.Node(
			#name='dataoutnode',
			#interface=nio.DataSink(
				#infields=[
					#'mat_file',
					#'fieldcoeff_file',
					#'mean_median_file']))
		#dataout.inputs.container = os.path.join(
			#inputnode.inputs.sub_id, inputnode.inputs.scan_id)
			
		#tbss2n.connect([
			#(inputnode, dataout,
				#[('parent_dir','base_directory')]),
			#(flirt, dataout, 
				#[("out_matrix_file", "@mat_file")]),
			#(fnirt, dataout, 
				#[("fieldcoeff_file", "@fieldcoeff_file")])
		#])
	#else:
		#print('%s output can only be found in nipype cache for workflow' % name)

	outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(
			fields=[
				"mat_list",
				"fieldcoeff_list",
				"mean_median_list"]))

	#Define workflow
	tbss2n.connect([
		(flirt, outputnode, [("out_matrix_file", "mat_list")]),
		(fnirt, sqrTmean, [('fieldcoeff_file','in_file')]),
		(fnirt, outputnode, [("fieldcoeff_file", "fieldcoeff_list")]),
		(sqrTmean, meanmedian, [('out_file','in_files')]),
		(meanmedian, outputnode, [("out_stat", "mean_median_list")])
		#(joinmats, outputnode, [('mat_list','mat_list')]),
		#(joinfields, outputnode, [('fieldcoeff_list','fieldcoeff_list')]),
		#(joinstats, outputnode, [('mean_median_list','mean_median_list')])
	])
	
	return tbss2n
	
	
def create_find_best(name="find_best", parent_dir=None):
	"""Find best target for FA warps, to minimize mean deformation
	
	Inputs
	------
	inputnode.fa_list
	inputnode.fields_lists
	inputnode.id_list
	inputnode.means_medians_lists
	All synced lists
	
	Outputs
	-------
	outputnode.best_id
	outputnode.best_fa
	outputnode.best_fa2MNI
	outputnode.best_fa2MNI_mat
	outputnode.2best_fields_list
	"""
	fb = pe.Workflow(name=name)
	if parent_dir is not None:
		fb.base_dir = parent_dir
	else:
		fb.base_dir = os.getcwd()
	
	inputnode = pe.Node(
		name='inputnode',
		interface=IdentityInterface(
			fields=[
				'fa_list',
				'fields_lists',
				'id_list',
				'means_medians_lists']))
				
	findbestnode = pe.Node(
		name='findbestnode',
		interface=Function(
			input_names=['id_list','list_numlists'],
			output_names=['best_index','best_id','best_mean','best_median'],
			function=find_best))
	
	selectfa = pe.Node(
		name='selectfa',
		interface=Select())
		
	selectfields = pe.Node(
		name='selectfields',
		interface=Select())
	
	fb.connect([
		(inputnode, findbestnode, 
			[('id_list','id_list'),
			('means_medians_lists','list_numlists')]),
		(inputnode, selectfa, [('fa_list','inlist')]),
		(inputnode, selectfields, [('fields_lists','inlist')]),
		(findbestnode, selectfa, [('best_index','index')]),
		(findbestnode, selectfields, [('best_index','index')])
		])
	
	#register best to MNI152
	bestmask = pe.Node(
		name='bestmask',
		interface=fsl.ImageMaths(op_string='-bin'))
		
	best2MNI = pe.Node(
		name='best2MNI',
		interface=fsl.FLIRT(dof=12))
		
	if fsl.no_fsl():
		warn('NO FSL found')
	else:
		best2MNI.inputs.reference = fsl.Info.standard_image(
			"FMRIB58_FA_1mm.nii.gz")
	
	#Group output to one node		
	outputnode = pe.Node(
		name='outputnode',
		interface=IdentityInterface(
			fields=[
				'best_id',
				'best_fa',
				'best_fa2MNI',
				'best_fa2MNI_mat',
				'2best_fields_list']))
			
	fb.connect([
		(selectfa, bestmask, [('out','in_file')]),
		(selectfa, best2MNI, [('out','in_file')]),
		(bestmask, best2MNI, [('out_file','in_weight')]),
		(best2MNI, outputnode,
			[('out_file','best_fa2MNI'),
			('out_matrix_file','best_fa2MNI_mat')]),
		(findbestnode, outputnode, [('best_id','best_id')]),
		(selectfa, outputnode, [('out','best_fa')]),
		(selectfields, outputnode, [('out','2best_fields_list')])
		])
	return fb


def create_tbss_3_postreg_find_best(name='tbss_3_postreg_find_best',
estimate_skeleton=True, target='best', suffix=None,
parent_dir=None, id_list=None, fa_list=None, field_list=None, mm_list=None,
writeFiles=False):
	"""find best target from fa_list, then apply warps
	
	Inputs
	------
	inputnode.parent_dir
	inputnode.id_list
	inputnode.fa_list
	inputnode.field_list (if target is best, list of lists)
	inputnode.means_medians_lists
	
	Outputs
	-------
	outputnode.groupmask
	outputnode.skeleton_file
	outputnode.meanfa_file
	outputnode.mergefa_file
	"""
	
	tbss3 = pe.Workflow(name=name)
	
	inputnode = pe.Node(
		name='inputnode',
		interface=IdentityInterface(
			fields=[
				'parent_dir',
				'id_list',
				'fa_list',
				'field_list',
				'means_medians_lists']))
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
		tbss3.base_dir = parent_dir
	else:
		inputnode.inputs.parent_dir = os.getcwd()
		tbss3.base_dir = os.getcwd()
	if id_list is not None:
		inputnode.inputs.id_list = id_list
	if fa_list is not None:
		inputnode.inputs.fa_list = fa_list
	if field_list is not None:
		inputnode.inputs.field_list = field_list
	if mm_list is not None:
		inputnode.inputs.means_medians_lists = mm_list
	
	#Apply warp to best
	applywarp = pe.MapNode(
		name='applywarp',
		interface=fsl.ApplyWarp(),
		iterfield=['in_file', 'field_file'])
		
	if fsl.no_fsl():
		warn('NO FSL found')
	else:
		applywarp.inputs.ref_file = fsl.Info.standard_image(
			"FMRIB58_FA_1mm.nii.gz")
		
	if target == 'best':
		#Find best target that limits mean deformation, insert before applywarp
		fb = create_find_best(name='fb')
		
		rename2target = pe.MapNode(
			name='rename2target',
			interface=Function(
				#seems to be input alphabetically, sep is only named kwarg
				#arg0=input_id, arg1=to, arg2=target_id, arg3=suffix
				input_names=['sep','arg0','arg1','arg2','arg3'],
				output_names=['string'],
				function=join_strs),
			iterfield=['arg0'])
		rename2target.inputs.sep = '_'
		rename2target.inputs.arg1 = 'to'
		if suffix is None:
			suffix = 'warp'
		rename2target.inputs.arg3 = suffix
			
		tbss3.connect([
			(inputnode, fb, 
				[('fa_list','inputnode.fa_list'),
				('field_list','inputnode.fields_lists'),
				('id_list','inputnode.id_list'),
				('means_medians_lists','inputnode.means_medians_lists')]),
			(inputnode, rename2target, 
				[('id_list','arg0')]),
			(inputnode, applywarp, 
				[('fa_list','in_file')]),
			(fb, rename2target, [('outputnode.best_id','arg2')]),
			(fb, applywarp, 
				[('outputnode.2best_fields_list','field_file'),
				('outputnode.best_fa2MNI_mat','postmat')]),
			(rename2target, applywarp, 
				[('string','out_file')])
		])
	elif target == 'FMRIB58_FA_1mm.nii.gz':
		tbss3.connect([
			(inputnode, applywarp, 
				[("fa_list", "in_file"),
				("field_list", "field_file")])
			])

        
	# Merge the FA files into a 4D file
	mergefa = pe.Node(
		name='mergefa',
		interface=fsl.Merge(dimension='t'))
		
	# Get a group mask
	groupmask = pe.Node(
		name='groupmask',
		interface=fsl.ImageMaths(
			op_string="-max 0 -Tmin -bin",
			out_data_type="char",
			suffix="_mask"))

	maskgroup = pe.Node(
		name='maskgroup',
		interface=fsl.ImageMaths(
			op_string="-mas",
			suffix="_masked"))
		
	# Create outputnode
	outputnode = pe.Node(
		name='outputnode',
		interface=IdentityInterface(
			fields=[
				'groupmask',
				'skeleton_file',
				'meanfa_file',
				'mergefa_file']))
		
	tbss3.connect([
		(applywarp, mergefa, [("out_file", "in_files")]),
		(mergefa, groupmask, [("merged_file", "in_file")]),
		(mergefa, maskgroup, [("merged_file", "in_file")]),
		(groupmask, maskgroup, [("out_file", "in_file2")]),
		])
		
	if estimate_skeleton:
		# Take the mean over the fourth dimension
		meanfa = pe.Node(
			name='meanfa',
			interface=fsl.ImageMaths(
				op_string="-Tmean",
				suffix="_mean"))

		# Use the mean FA volume to generate a tract skeleton
		makeskeleton = pe.Node(
		name='makeskeleton',
		interface=fsl.TractSkeleton(skeleton_file=True))
			
		tbss3.connect([
			(maskgroup, meanfa, [("out_file", "in_file")]),
			(meanfa, makeskeleton, [("out_file", "in_file")]),
			(groupmask, outputnode, [('out_file', 'groupmask')]),
			(makeskeleton, outputnode, [('skeleton_file', 'skeleton_file')]),
			(meanfa, outputnode, [('out_file', 'meanfa_file')]),
			(maskgroup, outputnode, [('out_file', 'mergefa_file')])
			])
	else:
		#$FSLDIR/bin/fslmaths $FSLDIR/data/standard/FMRIB58_FA_1mm -mas mean_FA_mask mean_FA
		maskstd = pe.Node(
			name='maskstd',
			interface=fsl.ImageMaths(
				op_string="-mas",
				suffix="_masked"))
		maskstd.inputs.in_file = fsl.Info.standard_image("FMRIB58_FA_1mm.nii.gz")

		#$FSLDIR/bin/fslmaths mean_FA -bin mean_FA_mask
		binmaskstd = pe.Node(
			name='binmaskstd',
			interface=fsl.ImageMaths(op_string="-bin"))

        #$FSLDIR/bin/fslmaths all_FA -mas mean_FA_mask all_FA
		maskgroup2 = pe.Node(
			name='maskgroup2',
			interface=fsl.ImageMaths(
				op_string="-mas",
				suffix="_masked"))

		tbss3.connect([
			(groupmask, maskstd, [("out_file", "in_file2")]),
			(maskstd, binmaskstd, [("out_file", "in_file")]),
			(maskgroup, maskgroup2, [("out_file", "in_file")]),
			(binmaskstd, maskgroup2, [("out_file", "in_file2")])
			])

		outputnode.inputs.skeleton_file = fsl.Info.standard_image("FMRIB58_FA-skeleton_1mm.nii.gz")
		tbss3.connect([
			(binmaskstd, outputnode, [('out_file', 'groupmask')]),
			(maskstd, outputnode, [('out_file', 'meanfa_file')]),
			(maskgroup2, outputnode, [('out_file', 'mergefa_file')])
			])
			
	#if writeFiles:
		#dataout = pe.MapNode(
			#name='dataout',
			#interface=nio.DataSink(
				#infields=[
					#'tbss3.@fa',
					#'tbss3.@meanfa',
					#'tbss3.@mergefa',
					#'tbss3.@skeleton',
					#'tbss3.@groupmask']),
			#iterfield=['tbss3.@fa'])
		#if estimate_skeleton:
			#tbss3.connect([
				#(inputnode, dataout, [('parent_dir','base_directory')]),
				#(applywarp, dataout, [('out_file','tbss3.@fa')]),
				#(meanfa, dataout, [('out_file', 'tbss3.@meanfa')]),
				#(maskgroup, dataout, [('out_file', 'tbss3.@mergefa')]),
				#(groupmask, dataout, [('out_file', 'tbss3.@groupmask')]),
				#(makeskeleton, dataout, [('skeleton_file', 'tbss3.@skeleton')])
			#])
		#else:
			#setattr(dataout.inputs, 'reg.@skeleton', 
				#fsl.Info.standard_image('FMRIB58_FA-skeleton_1mm.nii.gz'))
			#tbss3.connect([
				#(inputnode, dataout, [('parent_dir','base_directory')]),
				#(applywarp, dataout, [('out_file','tbss3.@fa')]),
				#(maskstd, dataout, [('out_file', 'tbss3.@meanfa')]),
				#(maskgroup2, dataout, [('out_file', 'tbss3.@mergefa')]),
				#(binmaskstd, dataout, [('out_file', 'tbss3.@groupmask')]),
				#(makeskeleton, dataout, [('skeleton_file', 'tbss3.@skeleton')])
				#])
	return tbss3
	

def create_tbss_prep(name='tbss_prep', parent_dir=None, scan_list=None):
	"""Preprocess DTI files to get FA files, erode them and create masks
	
	Inputs
	------
	innode.parent_dir
	innode.scan_list (iterable)
	
	Outputs
	-------
	tbss1.fa_list
	tbss1.mask_list
	tbss1.slices
	"""
	
	nscans=len(scan_list)
	prep = pe.Workflow(name=name)
	#try:
		#wd = os.path.abspath(os.path.join(parent_dir,name))
		#os.mkdir(wd)
	#except OSError, e:
		#if e.errno != os.errno.EEXIST:
			#raise
		#pass
	prep.base_dir = parent_dir
	
	innode = pe.Node(
		name='innode',
		interface=IdentityInterface(
			fields=[
				'parent_dir',
				'scan_list'],
			mandatory_inputs=True))
	if parent_dir is not None:
		innode.inputs.parent_dir = parent_dir
	if scan_list is not None:
		#innode.inputs.scan_list = scan_list
		innode.iterables = ('scan_list', scan_list)
		
	split = create_split_ids(name='split', sep='_')
	
	#get container directory	
	cn = pe.Node(
		name='cn',
		interface=Function(
			#arg0=sub_id, arg1=scan_id
			input_names=['sep','arg0','arg1'],
			output_names=['string'],
			function=join_strs))
	cn.inputs.sep='/'
	
	prep.connect([
		(innode, split, 
			[('scan_list','inputnode.scan_list')]),
		(split, cn,
			[('outputnode.sub_id','arg0'),
			('outputnode.scan_id','arg1')])
		])
	
	#FA creation workfow				
	fa = create_genFA(name='fa',grabFiles=True)
			
	faout = pe.Node(
		name='faout',
		interface=nio.DataSink(infields=[
			'prep.@eddyc','prep.@fa','prep.@v1','prep.@mask']))
	faout.inputs.substitutions = [('reoriented','ro'),('edc','ec')]
	faout.inputs.parameterization = False
	
	prep.connect([
		(innode, fa, 
			[('parent_dir','inputnode.parent_dir')]),
		(innode, faout,
			[('parent_dir','base_directory')]),
		(split, fa, 
			[('outputnode.sub_id','inputnode.sub_id'),
			('outputnode.scan_id','inputnode.scan_id'),
			('outputnode.uid','inputnode.uid')]),
		(cn, faout,
			[('string','container')]),
		(fa, faout, 
			[('outputnode.eddyc_file','prep.@eddyc'),
			('outputnode.mask_file','prep.@mask'),
			('outputnode.FA_file','prep.@fa'),
			('outputnode.V1_file','prep.@v1')]) ])
	
	#put FA_files in list, container in list = len(tbss1out.inputs.items()) same			
	fajoin = pe.JoinNode(
		name='fajoin',
		interface=IdentityInterface(
			fields=['fa_list','container_list']),
		joinsource='innode',
		joinfield=['fa_list','container_list'])
	
	#tbss1 workflow, erode, mask, slices		
	tbss1 = tbss.create_tbss_1_preproc(name='tbss1')
	
	tbss1out = pe.MapNode(
		name='tbss1out',
		interface=nio.DataSink(
			infields=[
			'tbss1.@fa','tbss1.@mask','tbss1.@slice']),
		iterfield=['container','tbss1.@fa','tbss1.@mask','tbss1.@slice'])
	#tbss1out.inputs.base_directory = innode.inputs.parent_dir
	tbss1out.inputs.parameterization = False
			
	prep.connect([
		(innode, tbss1out,
			[('parent_dir','base_directory')]),
		(fa, fajoin, 
			[('outputnode.FA_file','fa_list')]),
		(cn, fajoin,
			[('string','container_list')]),
		(fajoin, tbss1,
			[('fa_list','inputnode.fa_list')]),
		(fajoin, tbss1out,
			[('container_list','container')]),
		(tbss1, tbss1out, 
			[('outputnode.fa_list','tbss1.@fa'),
			('outputnode.mask_list','tbss1.@mask'),
			('outputnode.slices','tbss1.@slice')])
		])
	
	return prep
	
	
def tbss2_target(parent_dir=None, 
target=None, target_id=None, id_list=None, fa_list=None, mask_list=None):
	if (target is not None) and \
	(target_id is not None) and \
	(id_list is not None) and \
	(fa_list is not None) and \
	(mask_list is not None):
		from wf.main import create_tbss_2_reg_n
		"""Wrap tbss2 workflow in mapnode(functionnode) to iterate over fa_files
		"""
		tbss2n = create_tbss_2_reg_n(
			name='tbss2n', 
			parent_dir=parent_dir, 
			id_list=id_list,
			target=target,
			fa_list=fa_list,
			mask_list=mask_list)
		
		tbss2n.run(plugin='MultiProc', plugin_args={'n_procs': 2})
		mat_list = tbss2n.result.outputs.outputnode.mat_list
		fieldcoeff_list = tbss2n.result.outputs.outputnode.fieldcoeff_list
		mean_median_list = tbss2n.result.outputs.outputnode.mean_median_list
		
		return mat_list, fieldcoeff_list, mean_median_list
	
def create_tbss_reg(name='tbss_reg', parent_dir = None, scan_list = None):
	"""Register FA files to best representative, merge and average
	
	Inputs
	------
	name		:	Str
	parent_dir	:	Directory
	scan_list	:	List[Str] 
		(Scan ID, e.g. ['0004_MR1_DTIFIXED','CHD_114_01a_DTIFIXED'])
		
	Outputs
	-------
	reg			:	Nipype workflow
	
	reg = create_tbss_reg(name='tbss_reg',
	parent_dir='/home/pirc/Desktop/DWI/CHD_tractography/CHP',
	scan_list=['0761_MR1_30D_DTI','CHD_052_01a_DTIFIXED'])
	"""
	if parent_dir is None:
		msg='create_tbss_reg:parent_dir must be specified'
		raise NameError(msg)
	if (scan_list is None) or (not isinstance(scan_list, (list,tuple))):
		msg='create_tbss_reg:scan_list must be specified list or tuple'
		raise NameError(msg)
		
	nscans=len(scan_list)
	reg = pe.Workflow(name=name)
	#try:
		#wd = os.path.abspath(os.path.join(parent_dir,name))
		#os.mkdir(wd)
	#except OSError, e:
		#if e.errno != os.errno.EEXIST:
			#raise
		#pass
	reg.base_dir = parent_dir
	
	tbssprep = create_tbss_prep(name='tbssprep', 
		parent_dir=reg.base_dir, 
		scan_list=scan_list)
			
	tbss2 = pe.MapNode(
		name='tbss2',
		interface=Function(
			input_names=['parent_dir','target','target_id','id_list','fa_list','mask_list'],
			output_names=['mat_list','fieldcoeff_list','mean_median_list'],
			function=tbss2_target),
		iterfield=['target','target_id'])
	tbss2.inputs.id_list = scan_list
	tbss2.inputs.target_id = scan_list
	tbss2.inputs.parent_dir = parent_dir
		
	tbss2out = pe.MapNode(
		name='tbss2out',
		interface=nio.DataSink(
			infields=[
				'tbss2.@mat_file',
				'tbss2.@fieldcoeff_file',
				'tbss2.@mean_median_file']),
		iterfield=[
			'container',
			'tbss2.@mat_file',
			'tbss2.@fieldcoeff_file',
			'tbss2.@mean_median_file'])
	tbss2out.inputs.base_directory = parent_dir
			
	
	#list of tuples format with subnodes raised exception: unknown set of 
	#parameters with more than 2 levels. The following format works regardless
	#reg.connect(tbssprep, 'fa.inputnode.parent_dir',tbss2,'parent_dir')
	reg.connect(tbssprep,'tbss1.outputnode.fa_list',tbss2,'target')
	reg.connect(tbssprep,'tbss1.outputnode.fa_list',tbss2,'fa_list')
	reg.connect(tbssprep,'tbss1.outputnode.mask_list',tbss2,'mask_list')
	reg.connect(tbssprep,'cn.string',tbss2out,'container')
	#reg.connect(tbssprep,'fa.inputnode.parent_dir',tbss2out,'base_directory')
	reg.connect([
		(tbss2, tbss2out, 
			[('mat_list','tbss2.@mat_file'),
			('fieldcoeff_list','tbss2.@fieldcoeff_file'),
			('mean_median_list','tbss2.@mean_median_file')])
		])
		
	tbss3 = create_tbss_3_postreg_find_best(name='tbss3',
		target='best',parent_dir=parent_dir,id_list=scan_list,writeFiles=True)
		
	reg.connect(tbssprep,'tbss1.outputnode.fa_list',tbss3,'inputnode.fa_list')
	reg.connect(tbss2,'fieldcoeff_list',tbss3,'inputnode.field_list')
	
	tbss3out = pe.MapNode(
		name='tbss3out',
		interface=nio.DataSink(
			infields=[
				'tbss3.@groupmask',
				'tbss3.@skeleton',
				'tbss3.@meanfa',
				'tbss3.@mergefa']),
		iterfield=[
			'tbss3.@groupmask',
			'tbss3.@skeleton',
			'tbss3.@meanfa',
			'tbss3.@mergefa'])
	tbss3out.inputs.base_directory = parent_dir
			
	reg.connect(tbssprep,'cn.string',tbss3out,'container')
	#reg.connect(tbssprep,'fa.inputnode.parent_dir',tbss3out,'base_directory')
	reg.connect([
		(tbss3, tbss3out,
			[('outputnode.groupmask','tbss3.@groupmask'),
			('outputnode.skeleton_file','tbss3.@skeleton'),
			('outputnode.meanfa_file','tbss3.@meanfa'),
			('outputnode.mergefa_file','tbss3.@mergefa')])
		])

		
	return reg
	
