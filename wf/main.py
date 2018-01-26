from wf.DSI_Studio_base import *
from wf.utils import patient_scan, read_config, split_chpid
from nipype import IdentityInterface, SelectFiles, Function
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
from nipype.interfaces import fsl
from nipype.interfaces.utility import Rename, Select
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
		inputnode.iterables = ("scan_list", scan_list)
	else:
		print("inputnode.inputs.scan_list must be set before running")
			
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

def create_genFA(name="genFA",parent_dir=None,sub_id=None,scan_id=None,uid=None):
	
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
		prepin.inputs.parent_dir = parent_dir
	if sub_id is not None:
		prepin.inputs.sub_id = sub_id
	if scan_id is not None:
		prepin.inputs.scan_id = scan_id
	if uid is not None:
		prepin.inputs.uid = uid
	
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
		dwi="%s/%s/%s_%s_%s_ec.nii.gz",
		bval="%s/%s/%s_%s_%s.bval",
		bvec="%s/%s/%s_%s_%s.bvec")
	datain.inputs.template_args = dict(
		dwi=[['sub_id','scan_id','sub_id','scan_id','uid']],
		bval=[['sub_id','scan_id','sub_id','scan_id','uid']],
		bvec=[['sub_id','scan_id','sub_id','scan_id','uid']])
	datain.inputs.sort_filelist=True
	
	#Create Reorient2Std node
	reorient = pe.Node(
		name="reorient",
		interface=fsl.Reorient2Std())
	#reorient.inputs.in_file = datain.outputs.dwi
	
	#Create EddyCorrect node
	eddyc = pe.Node(
		name="eddyc",
		interface=fsl.EddyCorrect())
	eddyc.inputs.ref_num = 0
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

	joinmasks = pe.JoinNode(
		name='joinmasks',
		interface=IdentityInterface(
			fields=['mask_list'],
			mandatory_inputs=True),
		joinsource='rbet',
		joinfield=['mask_list'])
		
	joinfas = pe.JoinNode(
		name='joinfas',
		interface=IdentityInterface(
			fields=['fa_list'],
			mandatory_inputs=True),
		joinsource='dti',
		joinfield=['fa_list'])
	
	outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(
			fields=[
				"fa_list",
				"mask_list"],
			mandatory_inputs=True))
	#outputnode.inputs.fa_list = reduce(dti.inputs.FA)
	#outputnode.inputs.mask_list = reduce(rbet.outputs.mask_file)
	
	
	
	#Preprocess workflow
	gen_fa = pe.Workflow(name=name)
	gen_fa.connect([
		(inputnode, datain, [('sub_id','sub_id'),
							('scan_id','scan_id'),
							('uid','uid')]),
		(datain, reorient, [("dwi","in_file")]),
		(datain, dti, [("bvals", "bvals")]),
		(datain, dti, [("bvecs", "bvecs")]),
		(reorient, eddyc, [("out_file","in_file")]),
		(eddyc, rbet, [("eddy_corrected","in_file")]),
		(eddyc, dti, [("eddy_corrected","dwi")]),
		(rbet, dti, [("mask_file","mask")]),
		(rbet, joinmasks, [('mask_file','mask_list')]),
		(dti, joinfas, [("FA", "fa_list")]),
		(joinfas, outputnode, [('fa_list','fa_list')]),
		(joinmasks, outputnode, [("mask_list","mask_list")])
		])
	return gen_fa


def create_invwarp_all2best(name="invwarp_all2best",
	fadir=None, outdir=None):
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

def create_tbss_2_reg_n(name="tbss_2_reg_n", parent_dir=None):
	"""TBSS nonlinear registration:
	Performs flirt and fnirt from every file in fa_list to reference
	"""
	from nipype import IdentityInterface
	#TODO Finish conversion from mapnode
	inputnode = pe.Node(
		name="inputnode",
		interface=IdentityInterface(
			fields=[
				"sub_id",
				"scan_id",
				"uid",
				"fa_list",
				"mask_list",
				"reference"],
			mandatory_inputs=True))
	inputnode.iterables=("reference",inputnode.inputs.fa_list)
	
	refnode = pe.Node(
		name='refnode',
		interface=IdentityInterface(
			fields=['ref']))
	ref.iterables = ('ref', inputnode.inputs.fa_list)

	#Registration
	flirt = pe.Node(
		name="flirt",
		interface=fsl.FLIRT(dof=12),
		iterfield=[
			"in_file",
			"in_weight",
			"reference"])

	fnirt = pe.Node(
		name="fnirt",
		interface=fsl.FNIRT(fieldcoeff_file=True),
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
		iterfield=[
			"in_file",
			"ref_file",
			"affine_file",
			"fieldcoeff_file"])
			
	if fsl.no_fsl():
		warn('NO FSL found')
	else:
		config_file = os.path.join(os.environ["FSLDIR"],
									"etc/flirtsch/FA_2_FMRIB58_1mm.cnf")
		fnirt.inputs.config_file=config_file

	#Estimate mean & median deformation
	sqrTmean = pe.Node(
		name="sqrTmean",
		interface=fsl.ImageMaths(op_string="-sqr -Tmean"),
		iterfield=["in_file","out_file"])
	
	meanmedian = pe.Node(
		name="meanmedian",
		interface=fsl.ImageStats(op_string="-M -P 50"),
		iterfield=["in_files","output_root"])
	
	#Write files to directories	
	dataoutnode = pe.Node(
		name='dataoutnode',
		interface=nio.DataSink(
			infields=[
				'mat_file',
				'fieldcoeff_file',
				'mean_median_file']))
	if parent_dir is not None:
		dataoutnode.inputs.base_directory = parent_dir
		
	#Group files to lists of files
	joinmats = pe.JoinNode(
		name='joinmats',
		interface=IdentityInterface(
			fields=['mat_list'])
		joinsource='flirt',
		joinfield=['mat_list'])
		
	joinfields = pe.JoinNode(
		name='joinfields',
		interface=IdentityInterface(
			fields=['fieldcoeff_list'])
		joinsource='fnirt',
		joinfield=['field_list'])
		
	joinstats = pe.JoinNode(
		name='joinstats',
		interface=IdentityInterface(
			fields=['mean_median_list'])
		joinsource='meanmedian',
		joinfield=['mean_median_list'])

	outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(
			fields=[
				"mat_list",
				"fieldcoeff_list",
				"mean_median_list"]))

	#Define workflow
	tbss2n = pe.Workflow(name=name)
	tbss2n.connect([
		(inputnode, flirt, 
			[("fa_list","in_file"),
			("fa_list","reference"),
			("mask_list","in_weight")]),
		(inputnode, fnirt, 
			[("fa_list","in_file"),
			("fa_list","ref_file")]),
		(inputnode, dataoutnode, [("sub_id","container"),
			("scan_id","container.scan")]),
		(flirt, fnirt, [("out_matrix_file", "affine_file")]),
		(flirt, dataoutnode, [("out_matrix_file", "mat_file")]),
		(fnirt, dataoutnode, [("fieldcoeff_file", "fieldcoeff_file")]),
		(meanmedian, dataoutnode, [("out_stat", "mean_median_file")]),
		(flirt, joinmats, [("out_matrix_file", "mat_list")]),
		(fnirt, joinfields, [("fieldcoeff_file", "fieldcoeff_list")]),
		(meanmedian, joinstats, [("out_file", "mean_median_list")]),
		(joinmats, outputnode, [('mat_list','mat_list')]),
		(joinfields, outputnode, [('fieldcoeff_list','fieldcoeff_list')]),
		(joinstats, outputnode, [('mean_median_list','mean_median_list')])
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
			input_names=['id_list','mean_median_list'],
			output_names=['best_id','mean','median'],
			function=find_best))
			
	index = inputnode.inputs.ids_list.index(findbestnode.outputs.best_id)
			
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
			('means_medians_lists','mean_median_list')]),
		(inputnode, selectfanode, [('fa_list','in_list')]),
		(inputnode, selectfieldnode, [('field_list','in_list')]),
		(selectfanode, outputnode, [('out','best_fa')])
		(selectfieldnode, outputnode, [('out','best_field_list')])
		])
	return fb
	
def create_tbss_3_postreg_find_best(name='tbss_3_postreg_find_best',
	estimate_skeleton=True, target='FMRIB58_FA_1mm.nii.gz'):
	"""find best target from fa_list, then apply warps"""
	
	tbss3 = pe.Workflow(name=name)
	
	inputnode=pe.Node(
		name='inputnode',
		interface=IdentityInterface(
			fields=[
				'fa_list',
				'field_list',
				'id_list',
				'means_medians_lists']))
	
	#Apply warp to best
	applywarp = pe.MapNode(
		name='applywarp',
		interface=fsl.ApplyWarp(),
		iterfield=['in_file', 'field_file'])
		
	if target == 'FMRIB58_FA_1mm.nii.gz':
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

	else:
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

def tbss_reg(name='tbss_reg',
	parent_dir=None, fa_list=None):
		
	tbssin = pe.Node(
		name="tbssin",
		interface=IdentityInterface(
			fields=[
				"parent_dir",
				"fa_list"]))
	
	#Copy FA files to new directory
	
	#TBSS1
	tbss1 = create_tbss_1_preproc("tbss1")
	#inputnode.fa_list
	#outputnode.fa_list, outputnode.mask_list, outputnode.slices
	
	#TBSS2
	tbss2 = create_tbss_reg_n("tbss2")
	#inputnode.fa_list, inputnode.mask_list, inputnode.reference
	#outputnode.mat_list, outputnode.fieldcof_list, outputnode.mean_median_list
	
	#TBSS3
	tbss3 = create_tbss_3_postreg("tbss3")
	#inputnode.field_list, inputnode.fa_list
	#outputnode.groupmask, outputnode.skeleton_file,outputnode.meanfa_file
    #outputnode.mergefa_file
	
	tbssout = pe.Node(
		name="tbssout",
		interface=IdentityInterface(
			fields=[
				"best_target",
				"best_to_mni",
				"to_best_warp_list",
				"mni_fa_list"]))
	
	tbss = pe.Workflow(name=name)
	tbss.connect([
		(tbssin, tbss1, [("fa_list","inputnode.fa_list")]),
		(tbss1, tbss2, [("","")]),
		(tbss2, tbss3, [("","")]),
		(tbss2, tbssout [("","to_best_warp_list")]),
		(tbss3, tbssout [("","best_target")]),
		(tbss3, tbssout [("","best_to_mni")]),
		(tbss3, tbssout [("","mni_fa_list")])
		])


	return tbss

def tbss_reg(name='tbss_reg', parent_dir=None, scan_list=None):
	
	reg = pe.Workflow(name=name)
	try:
		wd = os.path.abspath(os.path.join(parent_dir,name))
		os.mkdir(wd)
	except OSError, e:
		if e.errno != os.errno.EEXIST:
			raise
		pass
	reg.base_dir = wd
	
	inputnode = pe.Node(
		name='inputnode',
		interface=IdentityInterface(
			fields=[
				'parent_dir',
				'scan_list'],
			mandatory_inputs=True))
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
	if scan_list is not None:
		inputnode.inputs.scan_list = scan_list
		
	split = create_split_ids(name='split', sep='_')
	
	reg.connect([
		(inputnode, split, [('parent_dir','inputnode.parent_dir'),
							('scan_list','inputnode.scan_list')]) ])
							
	fa = create_genFA(name='fa')
	
	reg.connect([
		(inputnode, fa, [('parent_dir','inputnode.parent_dir')]),
		(split, fa, [('outputnode.sub_id','inputnode.sub_id'),
					('outputnode.scan_id','inputnode.scan_id'),
					('outputnode.uid','inputnode.uid')]) ])
					
	tbss1 = tbss.create_tbss_1_preproc(name='tbss1')
	tbss2 = create_tbss_2_reg_n(name='tbss2')
	tbss3 = create_tbss_3_postreg_find_best(name='tbss3',
		target=tbss2.outputnode.best_fa)
	
	reg.connect([
		(fa, tbss1, [('outputnode.fa_list','inputnode.fa_list')]),
		(tbss1, tbss2, [('outputnode.fa_list','inputnode.fa_list'),
					('outputnode.mask_list','inputnode.mask_list')]),
		(tbss1, tbss3, [('outputnode.fa_list','inputnode.fa_list')]),
		(tbss2, tbss3, [('outputnode.fieldcoeff_list','inputnode.field_list')])
		])
	
	return reg
