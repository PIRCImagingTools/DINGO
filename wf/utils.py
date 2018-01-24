def flatten(l, ltypes=(list, tuple)):
	"""flatten lists and tuples to a single list"""
	ltype = type(l)
	l = list(l)
	i = 0
	while i < len(l):
		while isinstance(l[i], ltypes):
			if not l[i]:
				l.pop(i)
				i -= 1
				break
			else:
				l[i:i+1] = l[i]
		i += 1
	return ltype(l)

def list_to_str(sep=None, args=None):
	"""flattened args turned to str with separator
	default separator: ''"""
	if sep is None:
		sep=''
	if args is None:
		raise TypeError("Not enough arguments for str creation")
	return sep.join(str(e) for e in flatten(args))

#Return patient/scan id
def patient_scan(patientcfg, addSequence=None):
	"""Get patient/scan id

	Parameters
	----------
	patcfg : dict < json (patient config file with pid, scanid in top level)
	addSequence : bool (Flag to join sequence id with pid, scanid)

	Returns
	-------
	patient_scan_id : str (concatenated)
	"""

	if "pid" in patientcfg:
		patient_id = patientcfg["pid"]
	else:
		raise KeyError("patient_config:pid")
	if "scanid" in patientcfg:
		scan_id = patientcfg["scanid"]
	else:
		raise KeyError("patient_config:scanid")
	if addSequence == None:
		addSequence = False
	ps_id = []
	ps_id.append(patient_id)
	ps_id.append("_")
	ps_id.append(scan_id)

	if addSequence: #if True, default False
		if "sequenceid" in patientcfg:
			ps_id.append("_")
			seq_id = patientcfg["sequenceid"]
			ps_id.append(seq_id)
		else:
			raise KeyError("patient_config:sequenceid")
	patient_scan_id = "".join(ps_id)

	return patient_scan_id

#Split patient/scan id
def split_chpid(psid,sep):
	"""Returns patient/scan/uid from input id

	e.g. XXXX_YYYY_ZZZZ 			-> XXXX, YYYY, ZZZZ
		 XXXX_YYYY_ZZZZ_ZZZZ		-> XXXX, YYYY, ZZZZ_ZZZZ
		 CHD_XXXX_YYYY_ZZZZ 		-> CHD_XXXX, YYYY, ZZZZ
		 CHD_XXXX_YYYY_ZZZZ_ZZZZ 	-> CHD_XXXX, YYYY, ZZZZ_ZZZZ
"""
	if not isinstance(psid, str):
		raise TypeError("%s is not a string" % psid)
	if not isinstance(sep, str):
		raise TypeError("%s is not a string" % sep)

	splitid=psid.split(sep)
	if splitid[0] == "CHD":
		subind=0
		scanind=2
		uniind=3
	else:
		subind=0
		scanind=1
		uniind=2

	subid = "_".join(splitid[subind:scanind])
	scanid = "_".join(splitid[scanind:uniind])
	uniid = "_".join(splitid[uniind:])
	return subid, scanid, uniid


#Convert str to boolean
def tobool(s):
	"""Convert string/int true/false values to bool"""
	if isinstance(s, bool):
		return s
	if isinstance(y, str):
		sl = s.lower()
	if (sl == "true" or 
		sl == "t" or 
		sl == "y" or 
		sl == "yes" or 
		sl == "1" or 
		s == 1):
		return True
	elif (sl == "false" or 
		  sl == "f" or 
		  sl == "n" or 
		  sl == "no" or 
		  sl == "0" or 
		  s == 0):
		return False
	else:
		raise ValueError("%s cannot be converted to bool" % (s))


#Read config.json
def read_config(configpath):
	"""Read in json config file

	Parameters
	----------
	configpath : str (absolute path to file)

	Returns
	-------
	config : dict < json
	"""

	import logging
	import json
	logger = logging.getLogger(__name__)
	try:
		#configpath = os.path.join(filepath, filename)
		with open(configpath) as file:
			cfg = json.load(file)
			file.close()
	except Exception:
		logger.exception("Config file could not be read: " + configpath)
		raise
	return cfg

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
	method=1
	
	rec = DSIStudioReconstruct()
	rec.inputs.source = source
	rec.inputs.method = method
	return rec
