#Return patient/scan id
def patient_scan(patientcfg):
	"""Get patient/scan id

	Parameters
	----------
	patcfg : dict < json (patient config file with pid, scanid in top level)

	Outputs
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
	ps_id = []
	ps_id.append(patient_id)
	ps_id.append("_")
	ps_id.append(scan_id)
	patient_scan_id = "".join(ps_id)

	return patient_scan_id

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
		logger.exception("Config file not found: " + configpath)
		raise
	return cfg

def testvalues():
	syscfgpath = "/home/pirc/Desktop/DWI/DINGO/res/system_config.json"
	anacfgpath = "/home/pirc/Desktop/DWI/DINGO/res/Neonates_analysis_config.json"
	subcfgpath = "/home/pirc/Desktop/DWI/DINGO/res/patient_config.json"

	return syscfgpath, anacfgpath, subcfgpath
