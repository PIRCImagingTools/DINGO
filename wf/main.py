from wf.DSI_Studio_base import *
from wf.utils import patient_scan, read_config, split_chpid
from nipype import IdentityInterface, SelectFiles, Function
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
from nipype.interfaces import fsl
from nipype.interfaces.utility import Rename, Select, Split
from nipype.workflows.dmri.fsl import tbss


anacfgpath = '/home/pirc/Desktop/DWI/DINGO/res/Neonates_analysis_config.json'#os.environ["ana_config"]
anacfg = read_config(anacfgpath)


#Check for included sub/scan list
if "included_psids" in anacfg:
	scanlist = anacfg["included_psids"]
	t_scanlist = frozenset(scanlist)
else:
	raise KeyError("included_psids not identified in analysis config")

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
			fields=["parent_dir",
					"scan_list"],
			mandatory_inputs=True))
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
	else:
		inputnode.inputs.parent_dir = os.getcwd()
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
			fields=["parent_dir",
					"sub_id",
					"scan_id",
					"uid"],
			mandatory_inputs=True))
			
	#Create Workflow
	splitids = pe.Workflow(name=name)
	splitids.connect([
		(inputnode, splitidsnode, 
			[("scan_list", "psid")]),
		(inputnode, outputnode, 
			[("parent_dir", "parent_dir")]),
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
	grabFiles=False, writeFiles=False):
	
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
		
	genFA = pe.Workflow(name=name,
		base_dir='%s/%s/%s/%s' % 
			(parent_dir,name,inputnode.inputs.sub_id,inputnode.inputs.scan_id))
	
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
	dti = pe.Node(
		name="dti",
		interface=fsl.DTIFit())
	#dti.inputs.base_name = patient_scan(sbc, addSequence=True)
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
		#datain.inputs.base_directory = inputnode.inputs.parent_dir
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
			
	#if writeFiles:
		#dataout = pe.Node(
			#name='dataout',
			#interface=nio.DataSink())
		#fileprefix = []
		#fileprefix.extend((
			#inputnode.inputs.sub_id,
			#inputnode.inputs.scan_id,
			#inputnode.inputs.uid))
		#fileprefix = '_'.join(fileprefix)
		#dataout.inputs.substitutions = [
			#('reoriented','reor'),
			#('dtifit_',fileprefix)]
		#dataout.inputs.container = os.path.join(
			#inputnode.inputs.sub_id, inputnode.inputs.scan_id)
		#genFA.connect([
			#(inputnode, dataout, [('parent_dir','base_directory')]),
			#(eddyc, dataout, [('eddy_corrected','@eddyc')]),
			#(rbet, dataout, [('mask_file','@mask')]),
			#(dti, dataout, [('FA','@FA'),
							#('V1','@V1')])
			#])
	#else:
		#print('%s output can only be found in nipype cache for workflow' % name)
			
	joinmasks = pe.JoinNode(
		name='joinmasks',
		interface=IdentityInterface(
			fields=['mask_list'],
			mandatory_inputs=True),
		joinsource='rbet',
		joinfield=['mask_list'])
		
	joindti = pe.JoinNode(
		name='joinfas',
		interface=IdentityInterface(
			fields=['FA_list','V1_list'],
			mandatory_inputs=True),
		joinsource='dti',
		joinfield=['FA_list','V1_list'])
	
	outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(
			fields=[
				"eddyc_list",
				"FA_list",
				"V1_list",
				"mask_list"],
			mandatory_inputs=True))
	#outputnode.inputs.fa_list = reduce(dti.inputs.FA)
	#outputnode.inputs.mask_list = reduce(rbet.outputs.mask_file)
	
	#Preprocess workflow
	genFA.connect([
		(reorient, eddyc, [("out_file","in_file")]),
		(eddyc, rbet, [("eddy_corrected","in_file")]),
		(eddyc, dti, [("eddy_corrected","dwi")]),
		(rbet, dti, [("mask_file","mask")]),
		(rbet, joinmasks, [('mask_file','mask_list')]),
		(dti, joindti, [("FA", "FA_list"),
						('V1','V1_list')]),
		(joindti, outputnode, [('FA_list','FA_list'),
								('V1_list','V1_list')]),
		(joinmasks, outputnode, [("mask_list","mask_list")])
		])
	return genFA


def create_invwarp_all2best(name="invwarp_all2best",fadir=None, outdir=None):
	"""Calculate inverse warps of files"""
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
		
	invwarpwf = pe.Workflow(name=name)
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

def create_tbss_2_reg_n(name="tbss_2_reg_n", parent_dir=None, 
	grabFiles=False, writeFiles=False):
	"""TBSS nonlinear registration:
	Performs flirt and fnirt from every file in fa_list to a target
	sub_id, scan_id, uid define target, will result in target warp to itself 
	just like tbss scripts
	"""
	tbss2n = pe.Workflow(name=name)
	
	#TODO Finish conversion from mapnode
	inputnode = pe.Node(
		name="inputnode",
		interface=IdentityInterface(
			fields=[
				"parent_dir",
				"sub_id",
				"scan_id",
				"uid",
				"fa_list",
				"mask_list",
				"target"]))
	#inputnode.iterables([
		#('fa_list', inputnode.fa_list),
		#('mask_list', inputnode.mask_list)])
	#inputnode.synchronize = True
	
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
	else:
		inputnode.inputs.parent_dir = os.getcwd()
			

	#Registration
	flirt = pe.MapNode(
		name="flirt",
		interface=fsl.FLIRT(dof=12),
		iterfield=['in_file','in_weight'])

	fnirt = pe.MapNode(
		name="fnirt",
		interface=fsl.FNIRT(fieldcoeff_file=True),
		iterfield=['in_file', 'inmask_file', 'affine_file'])
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
		
	#Group files to lists of files
	#joinmats = pe.JoinNode(
		#name='joinmats',
		#interface=IdentityInterface(
			#fields=['mat_list']),
		#joinsource='flirt',
		#joinfield=['mat_list'])
		
	#joinfields = pe.JoinNode(
		#name='joinfields',
		#interface=IdentityInterface(
			#fields=['fieldcoeff_list']),
		#joinsource='fnirt',
		#joinfield=['field_list'])
		
	#joinstats = pe.JoinNode(
		#name='joinstats',
		#interface=IdentityInterface(
			#fields=['mean_median_list']),
		#joinsource='meanmedian',
		#joinfield=['mean_median_list'])

	outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(
			fields=[
				"mat_list",
				"fieldcoeff_list",
				"mean_median_list"]))

	#Define workflow
	tbss2n.connect([
		(inputnode, flirt, 
			[("fa_list","in_file"),
			("fa_list","reference"),
			("mask_list","in_weight")]),
		(inputnode, fnirt, 
			[("fa_list","in_file"),
			("fa_list","ref_file")]),
		(flirt, fnirt, [("out_matrix_file", "affine_file")]),
		(fnirt, sqrTmean, [('fieldcoeff_file','in_file')]),
		(sqrTmean, meanmedian, [('out_file','in_files')]),
		(flirt, outputnode, [("out_matrix_file", "mat_list")]),
		(fnirt, outputnode, [("fieldcoeff_file", "fieldcoeff_list")]),
		(meanmedian, outputnode, [("out_stat", "mean_median_list")])
		#(joinmats, outputnode, [('mat_list','mat_list')]),
		#(joinfields, outputnode, [('fieldcoeff_list','fieldcoeff_list')]),
		#(joinstats, outputnode, [('mean_median_list','mean_median_list')])
	])
	
	return tbss2n
	
def create_find_best(name="find_best"):
	"""Find best target for FA warps, to minimize mean deformation"""
	fb = pe.Workflow(name=name)
	
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
			
	index = findbestnode.outputs.best_index
			
	selectfanode = pe.Node(
		name='selectfanode',
		interface=Select())
	selectfanode.inputs.index = index
		
	selectfieldnode = pe.Node(
		name='selectfieldnode',
		interface=Select())
	selectfieldnode.inputs.index = index
			
	outputnode = pe.Node(
		name='outputnode',
		interface=IdentityInterface(
			fields=[
				'best_fa',
				'best_field_list']))
			
	fb.connect([
		(inputnode, findbestnode, 
			[('id_list','id_list'),
			('means_medians_lists','list_numlists')]),
		(inputnode, selectfanode, [('fa_list','in_list')]),
		(inputnode, selectfieldnode, [('field_list','in_list')]),
		(selectfanode, outputnode, [('out','best_fa')])
		(selectfieldnode, outputnode, [('out','best_field_list')])
		])
	return fb
	
def create_tbss_3_postreg_find_best(name='tbss_3_postreg_find_best',
	estimate_skeleton=True, target='best', 
	parent_dir=None, writeFiles=False):
	"""find best target from fa_list, then apply warps"""
	
	tbss3 = pe.Workflow(name=name)
	
	inputnode=pe.Node(
		name='inputnode',
		interface=IdentityInterface(
			fields=[
				'parent_dir',
				'fa_list',
				'field_list',
				'id_list',
				'means_medians_lists']))
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
	else:
		inputnode.inputs.parent_dir = os.getcwd()
	
	#Apply warp to best
	applywarp = pe.MapNode(
		name='applywarp',
		interface=fsl.ApplyWarp(),
		iterfield=['in_file', 'field_file'])
		
	if target == 'best':
		#Find best target that limits mean deformation
		fb = create_find_best(name='fb')
		tbss3.connect([
			(inputnode, fb, 
				[('fa_list','inputnode.fa_list'),
				('field_list','inputnode.fields_lists'),
				('id_list','inputnode.id_list'),
				('means_medians_lists','inputnode.means_medians_lists')]),
			(fb, applywarp, 
				[('outputnode.best_fa','ref_file'),
				('outputnode.best_field_list','field_file')])
		])
	elif target == 'FMRIB58_FA_1mm.nii.gz':
		tbss3.connect([
			(inputnode, applywarp, 
				[("fa_list", "in_file"),
				("field_list", "field_file")])
			])
			
		if fsl.no_fsl():
			warn('NO FSL found')
		else:
			applywarp.inputs.ref_file = fsl.Info.standard_image(
				"FMRIB58_FA_1mm.nii.gz")

        
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
		
	tbss3 = pe.Workflow(name=name)
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
			
	if writeFiles:
		dataout = pe.MapNode(
			name='dataout',
			interface=nio.DataSink(infields=[
				'reg.@fa',
				'reg.@meanfa',
				'reg.@mergefa',
				'reg.@skeleton',
				'reg.@groupmask']))
		if estimate_skeleton:
			tbss3.connect([
				(inputnode, dataout, [('parent_dir','base_directory')]),
				(applywarp, dataout, [('out_file','reg.@fa')]),
				(meanfa, dataout, [('out_file', 'reg.@meanfa')]),
				(maskgroup, dataout, [('out_file', 'reg.@mergefa')]),
				(groupmask, dataout, [('out_file', 'groupmask')]),
				(makeskeleton, dataout, [('skeleton_file', 'reg.@skeleton')])
			])
		else:
			setattr(dataout.inputs, 'reg.@skeleton', 
				fsl.Info.standard_image('FMRIB58_FA-skeleton_1mm.nii.gz'))
			tbss3.connect([
				(inputnode, dataout, [('parent_dir','base_directory')]),
				(applywarp, dataout, [('out_file','reg.@fa')]),
				(maskstd, dataout, [('out_file', 'reg.@meanfa')]),
				(maskgroup2, dataout, [('out_file', 'reg.@mergefa')]),
				(binmaskstd, dataout, [('out_file', 'groupmask')]),
				(makeskeleton, dataout, [('skeleton_file', 'reg.@skeleton')])
			])
	return tbss3


def create_tbss_reg(name='tbss_reg', parent_dir=None, scan_list=None):
	
	nscans=len(scan_list)
	reg = pe.Workflow(name=name)
	try:
		wd = os.path.abspath(os.path.join(parent_dir,name))
		os.mkdir(wd)
	except OSError, e:
		if e.errno != os.errno.EEXIST:
			raise
		pass
	reg.base_dir = wd
	
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
		innode.inputs.scan_list = scan_list
		innode.iterables = ('scan_list', innode.inputs.scan_list)
		
	split = create_split_ids(name='split', sep='_')
	
	reg.connect([
		(innode, split, [('parent_dir','inputnode.parent_dir'),
							('scan_list','inputnode.scan_list')]) ])
							
	fa = create_genFA(name='fa',grabFiles=True)
	faout = pe.MapNode(
		name='faout',
		interface=nio.DataSink(infields=['@eddyc','@fa','@v1','@mask']),
		iterfield=['@eddyc','@fa','@v1','@mask'])
	faout.inputs.substitutions=[('reoriented','reor')]
								#('dtifit_',fileprefix)]
	faout.inputs.base_directory = innode.inputs.parent_dir
	
	reg.connect([
		(innode, fa, [('parent_dir','inputnode.parent_dir')]),
		(split, fa, [('outputnode.sub_id','inputnode.sub_id'),
					('outputnode.scan_id','inputnode.scan_id'),
					('outputnode.uid','inputnode.uid')]) ])
					
	tbss1 = tbss.create_tbss_1_preproc(name='tbss1')
	
	tbss1out = pe.MapNode(
		name='tbss1out',
		interface=nio.DataSink(
			infields=['tbss1.@fa','tbss1.@mask','tbss1.@slice']),
		iterfield=['tbss1.@fa','tbss1.@mask','tbss1.@slice'])
			
	reg.connect([
		(tbss1, tbss1out, [('outputnode.fa_list','tbss1.@fa')]),
		(tbss1, tbss1out, [('outputnode.mask_list','tbss1.@mask')]),
		(tbss1, tbss1out, [('outputnode.slices','tbss1.@slice')])
		])
		
	reg.run()
	
	iteratefas = pe.Node(
		name='iteratefas',
		interface=IdentityInterface,
			fields=['fa_list'])
			
	reg.connect([
		(tbss1, iteratefas, [('outputnode.fa_list','fa_list')])
		])
	iteratefas.iterables=('fa_list', tbss1.inputs.outputnode.inputs.fa_list)
	tbss2 = create_tbss_2_reg_n(name='tbss2',writeFiles=True)
	
	reg.connect([
		(tbss1, tbss2, [
			('outputnode.fa_list','inputnode.fa_list'),
			('outputnode.mask_list','inputnode.mask_list')]),
		(iteratefas,tbss2, [('fa_list','target')])
		])
			
	reg.run()
		
	tbss3 = create_tbss_3_postreg_find_best(name='tbss3',
		target=tbss2.inputs.outputnode.inputs.best_fa,writeFiles=True)
	
	reg.connect([
		(fa, tbss1, 
			[('outputnode.fa_list','inputnode.fa_list')]),
		(tbss1, tbss2, 
			[('outputnode.fa_list','inputnode.fa_list'),
			('outputnode.mask_list','inputnode.mask_list')]),
		(tbss1, tbss3, 
			[('outputnode.fa_list','inputnode.fa_list')]),
		(tbss2, tbss3, 
			[('outputnode.fieldcoeff_list','inputnode.field_list')])
		])
	
	return reg
