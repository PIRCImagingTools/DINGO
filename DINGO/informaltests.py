from DINGO.wf.DSI_Studio_base import (DSIStudioSource, DSIStudioReconstruct,
									DSIStudioTrack, DSIStudioAnalysis)
from DINGO.utils import read_config

def testconfigs():
	syscfgpath = "/home/pirc/Desktop/DWI/DINGO/res/system_config.json"
	anacfgpath = "/home/pirc/Desktop/DWI/DINGO/res/Neonates_analysis_config.json"
	subcfgpath = "/home/pirc/Desktop/DWI/DINGO/res/patient_config.json"

	syscfg = read_config(syscfgpath)
	anacfg = read_config(anacfgpath)
	subcfg = read_config(subcfgpath)

	return syscfg, anacfg, subcfg

def testtrk():
	from wf.DSI_Studio_base import DSIStudioTrack
	action = "trk"
	source = '/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/0003_20150225_DTIFIXED.nii.src.gz.012fy.dti.fib.gz'
	output = '/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Tracts/testGenu_sub.trk.gz'
	export = ['stat']
	
	rois = ['/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_Genu.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_Sagittal_L.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_Sagittal_R.nii.gz']
	roi_atlas = ['JHU-WhiteMatter-labels-1mm','JHU-WhiteMatter-labels-1mm']
	roi_ar = ['Genu_of_corpus_callosum','Splenium_of_corpus_callosum']
	roas = ['/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_PosteriorGenu.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_InternalCapsule_L.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_InternalCapsule_R.nii.gz']
	end_ar = ['Precentral_L','Genu_of_corpus_callosum']
	end_atlas = ['aal','JHU-WhiteMatter-labels-1mm']
	end_actions = [['dilation'],[]]
	roi_actions = [['dilation','dilation','smoothing'],[],['defragment'],[],['negate']]
	
	
	fat = 0.07
	fibc = 5000
	seedc = 10000000
	method = 0
	threads = 4
	
	trk = DSIStudioTrack()
#	trk.inputs.action = action
	trk.inputs.source = source
	trk.inputs.track = output
	trk.inputs.export = export
	trk.inputs.roi = rois
	trk.inputs.roi_actions = roi_actions
	trk.inputs.roi_ar = roi_ar
	trk.inputs.roi_atlas = roi_atlas
	trk.inputs.roa = roas
	trk.inputs.end_ar = end_ar
	trk.inputs.end_atlas = end_atlas
	trk.inputs.end_actions = end_actions
	
	trk.inputs.fa_threshold = fat
	trk.inputs.fiber_count = fibc
	trk.inputs.seed_count = seedc
	trk.inputs.method = method
	trk.inputs.thread_count = threads
	return trk

def testtrk2():
	from wf.DSI_Studio_base import DSIStudioTrack
	source = '/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/0003_20150225_DTIFIXED.nii.src.gz.012fy.dti.fib.gz'
	output = '/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Tracts/testGenu_sub_smallc.trk.gz'
	rois = ['/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_Genu.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_Sagittal_L.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_Sagittal_R.nii.gz']
	roas = ['/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_PosteriorGenu.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_InternalCapsule_L.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/CHP_mFAlap_InternalCapsule_R.nii.gz']
	action = "foo"
	fat = 0.1
	fibc = 10
	seedc = 5000
	method = 1
	threads = 1
	seed_plan = 1
	
	trk = DSIStudioTrack()
	trk.inputs.action = action
	trk.inputs.source = source
	trk.inputs.track = output
	trk.inputs.roi = rois
	trk.inputs.roa = roas
	trk.inputs.fa_threshold = fat
	trk.inputs.fiber_count = fibc
	trk.inputs.seed_count = seedc
	trk.inputs.method = method
	trk.inputs.thread_count = threads
	trk.inputs.seed_plan = seed_plan
	return trk

def testtrk3():
	from wf.DSI_Studio_base import DSIStudioTrack
	source = '/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/0003_20150225_DTIFIXED.nii.src.gz.fy.dti.fib.gz'
	output = '/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Tracts/testGenu_subrot.trk.gz'
	rois = ['/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/Genu.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/Sagittal_L.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/Sagittal_R.nii.gz']
	roas = ['/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/PosteriorGenu.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/InternalCapsule_L.nii.gz',
			'/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/Regions/InternalCapsule_R.nii.gz']
	roi_actions = [['dilation','dilation','smoothing'],[],['defragment']]
	fat = 0.07
	fibc = 5000
	seedc = 100000000
	method = 0
	threads = 4
	
	trk = DSIStudioTrack()
	trk.inputs.source = source
	trk.inputs.track = output
	trk.inputs.roi = rois
	#trk.inputs.roi_actions = roi_actions
	trk.inputs.roa = roas
	trk.inputs.fa_threshold = fat
	trk.inputs.fiber_count = fibc
	trk.inputs.seed_count = seedc
	trk.inputs.method = method
	trk.inputs.thread_count = threads
	return trk

def testrec():
	from wf.DSI_Studio_base import DSIStudioReconstruct
	source='/home/pirc/Desktop/DWI/CHD_tractography/CHP/0003/20150225/0003_20150225_DTIFIXED.src.gz'
	method='dti'
	
	rec = DSIStudioReconstruct()
	rec.inputs.source = source
	rec.inputs.method = method
	return rec

def testcn(parent_dir=None, scan_list=None):
	import nipype.pipeline.engine as pe
	from nipype import IdentityInterface, Function
	from wf.main import create_split_ids
	
	wf=pe.Workflow(name='wf')
	
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
		innode.iterables = ('scan_list', scan_list)
		
	split = create_split_ids(name='split', sep='_')
		
	cn = pe.Node(
		name='containernode',
		interface=Function(
			input_names=['sep','arg1','arg2'],
			output_names=['string'],
			function=join_strs))
	cn.inputs.sep='/'
	
	
	wf.connect([
		(innode,split,
			[('scan_list','inputnode.scan_list')]),
		(split,cn,
			[('outputnode.sub_id','arg1'),
			('outputnode.scan_id','arg2')])
		])

	return wf
