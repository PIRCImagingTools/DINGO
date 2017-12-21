from nipype import Node, Function
import os
import glob



#Create DSI studio tracking function
def DSI_TRK(syscfgpath, anacfgpath, subcfgpath):
	"""Run DSI studio tracking on command line
	
	Parameters
	----------
	syscfgpath : str (abspath to system config)
	anacfgpath : str (abspath to analysis config)
	subcfgpath : str (abspath to subject config)

	Outputs
	-------
	trk : .trk.gz file for each tract in anacfg, put in Regionsdir from
		subcfg
	"""
	
	import os
	import subprocess
	import logging

	#Get cfg json
	syscfg = read_config(syscfgpath)
	anacfg = read_config(anacfgpath)
	subcfg = read_config(subcfgpath)

	#Check if sub/scan is included in this group for analysis
	scanlist = anacfg["included_psids"]
	t_scanlist = frozenset(scanlist)
	ps_id = patient_scan(subcfg)
	t_pat_scan = frozenset([ps_id])

	if not bool(t_scanlist.intersection(t_sub_scan)):
		print "%s: SKIPPED - not part of Method" % (ps_id)
		return

	#Get needed values from anacfg
	try:
		ana_id = anacfg["method"]
		opts = anacfg["track_opts"]
		for tract in anacfg["tracts"]:
			print tract
			#Make the commandline string to call DSI Studio
			TRKCALL = gen_DSISTUDIO_cmd("trk", tract, anacfg, subcfg)

			#Call DSI Studio
			if not TRKCALL: #False if empty
				subprocess.call(TRKCALL)
	except Exception:
		logger.exception("Error fiber tracking: %s" % (ps_id))
		raise



#Create command line string to run
def gen_DSISTUDIO_cmd(action, tract, syscfg, anacfg, subcfg):
	
	"""Returns string to be called that will execute needed dsi_studio cmd
	
	Parameters
	----------
	action : str (3 letter action code)
	tract : str (tract identifier)
	anacfg : dict<json (contains method information, rois, roas, fa and angle thresholds, dsi studio path)
	subcfg : dict<json (contains paths for input and output)
	opts : dict (changes to default arguments for action)
	"""		

	import os
	import numbers

	ps_id = patient_scan(subcfg)
	tracts_base = os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], 
											   subcfg["paths"]["dti_dir"],
											   subcfg["paths"]["tracts"],
											   anacfg["method"]["name"]))
	cmd = []
	base_cmd = syscfg["dsi_studio"]["path"]
	action_cmd = " --action=%s" % (action)

	#Check relevant config file keys

	if "method" in anacfg:
		if "dsi_studio" in anacfg["method"]:
			if not "path" in syscfg["dsi_studio"]:
				print "DSI_Studio path unspecified"
				raise KeyError("syscfg:dsi_studio:path")
		else:
			raise KeyError("anacfg:method:dsi_studio")
	else:
		raise KeyError("anacfg:method")


	if not "pid" in subcfg:
		print "Patient ID unspecified"
		raise KeyError("subcfg:pid")

	if not "scanid" in subcfg:
		print "Scan ID unspecified"
		raise KeyError("subcfg:scanid")


	if "paths" in subcfg:
		if not "dti_dir" in subcfg["paths"]:
			print "DTI directory unspecified"
			raise KeyError("%s:paths:dti_dir" % (ps_id))
		if not "dti" in subcfg["paths"]:
			print "DTI file unspecified"
			raise KeyError("%s:paths:dti" % (ps_id))
	else:
		raise KeyError("%s:paths" % (ps_id))

	

	##### FIBER TRACKING ACTION #####
	if action == "trk":
		if not "tracts" in subcfg["paths"]:
			print "Tract directory unspecified"
			raise KeyError("%s:paths:tracts" % (ps_id))
		if not "fib" in subcfg["paths"]:
			print "Fiber Tracking file unspecified"
			raise KeyError("%s:paths:fib" % (ps_id))
		#set defaults
		d = dict(fiber_count = " --fiber_count=5000", #endcriterion
			 seed_count = " --seed_count=100000", #end criterion
			 thread_count = " --thread_count=1", #threads to run
			 method = " --method=0", #0:streamline, 1:rk4
			 initial_dir = " --initial_dir=0", #0:primary fiber, 1:random, 2:all fiber orientations
			 seed_plan = " --seed_plan=0", #0:subvoxel random, 1:voxelwise center
			 interp = " --interpolation=0", #direction interpolation 0:trilinear, 1:gaussian radial, 2:nearest neighbor
			 random_seed = " --random_seed=0", #0:off, 1:on
			 step_size = " --step_size=0.5", #move distance in tracking interval
			 turning_angle = " --turning_angle=60", #degrees
			 #interpo_angle = " --interpo_angle=0", #I don't yet understand this
			 fa_threshold = " --fa_threshold=0.1",
			 smoothing = " --smoothing=0", #incoming direction influence on propagation
			 min_length = " --min_length=15", #mm
			 max_length = " --max_length=500") #mm
		
		#update with input
		for k in d.keys():
			if k in anacfg["tracts"][tract]:
				part = d[k].partition("=")
				if isinstance(anacfg["tracts"][tract][k],str):
					d[k] = part[0]+part[1]+anacfg["tracts"][tract][k]
				elif isinstance(anacfg["tracts"][tract][k],numbers.Real):
					d[k] = part[0]+part[1]+str(anacfg["tracts"][tract][k])



		#set required argument strings
		source_cmd = " --source=%s" % \
					 os.path.abspath(os.path.join(subcfg["paths"]["base_dir"],
												  subcfg["paths"]["dti_dir"],
												  subcfg["paths"]["fib"]))

		output_cmd = " --output=%s_%s.trk.gz" % (tracts_base, tract)

		regions_cmd = gen_regions_cmd(tract, anacfg, subcfg)

		post_process_cmd = gen_post_process_cmd(action, anacfg, subcfg)

		#dvals = "".join(d.values())

		cmd = [base_cmd,
			   action_cmd,
			   source_cmd,
			   output_cmd]

		for region in regions_cmd:
			cmd.append(region)
		for pp in post_process_cmd:
			cmd.append(pp)
		for val in d.values():
			cmd.append(val)

	
	##### ANALYSIS ACTION #####
	elif action == "ana":
		print "Working on this"
		source_cmd = " --source=%s_%s.trk.gz" % (tracts_base, tract)

		output_cmd = ""
		if "output" in anacfg["method"]["dsi_studio"]["actions"]["ana"]:
			output_cmd = " --output=%s_%s%s" % \
						 (tracts_base,
						  tract,
						  anacfg["method"]["dsi_studio"]["actions"]["ana"]["output"])
		
		regions_cmd = gen_regions_cmd(tract, anacfg, subcfg)

		post_process_cmd = gen_post_process_cmd(action, anacfg, subcfg)
		
		cmd = [base_cmd,
			   action_cmd,
			   source_cmd,
			   output_cmd] 

		for region in regions_cmd:
			cmd.append(region)
		for pp in post-process_cmd:
			cmd.append(pp)

	else: #unrecognized action
		print action + ": gen cmd not yet implemented for action"
	return cmd




#subfunction of gen_DSISTUDIO_cmd, used by trk and ana actions
def gen_regions_cmd(tract, anacfg, subcfg):
	import os

	ps_id = patient_scan(subcfg)
	regions_cmd = []
	regions_base = os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], 
			   									subcfg["paths"]["dti_dir"], 
												subcfg["paths"]["regions"], 
												anacfg["method"]["name"]))
	
	if not "regions" in subcfg["paths"]:
		print "Regions directory unspecified"
		raise KeyError("%s:paths:regions" % (ps_id))

	#set region options
	seed = "" #default is whole brain
	if "seed_mask" in anacfg["tracts"][tract]:
		seed = " --seed=%s_%s.nii.gz" % (regions_base, anacfg["tracts"][tract]["seed_mask"])
		regions_cmd.append(seed)

	i = 1
	rois = ""
	if "inclusion_masks" in anacfg["tracts"][tract]:
		rois = []
		for roi in anacfg["tracts"][tract]["inclusion_masks"]:	
			if i == 1:
				num=""#first roi argument has no numeral, --roi
			elif i > 5:
				print "More than 5 rois detected, check analysis config file"
				break
			else:
				num=i#further roi arguments go --roi2, --roi3
			regions_cmd.append(" --roi%s=%s_%s.nii.gz" % (num, regions_base, roi))
			i += 1
	

	i = 1
	roas = ""
	if "exclusion_masks" in anacfg["tracts"][tract]:
		roas = []
		for roa in anacfg["tracts"][tract]["exclusion_masks"]:	
			if i == 1:
				num=""#first roa argument has no numeral, --roa
			else:
				num=i#further roa arguments go --roa2, --roa3
			regions_cmd.append(" --roa%s=%s_%s.nii.gz" % (num, regions_base, roa))
			i += 1
	

	i = 1
	ends = ""
	if "ends_masks" in anacfg["tracts"][tract]:
		ends = []
		for end in anacfg["tracts"][tract]["ends_masks"]:
			if i == 1:
				num=""#first end argument has no numeral
			elif i == 2:
				num=i#second end argument is end2
			elif i > 2:#cannot have more than 2 ends
				print "More than 2 ends detected, check analysis config file"
				break
			regions_cmd.append(" --end%s=%s_%s.nii.gz" % (num, regions_base, end))
			i += 1
	

	ter = ""
	if "terminative_mask" in anacfg["tracts"][tract]:
		ter = " --ter=%s_%s.nii.gz" % (regions_base, anacfg["tracts"][tract]["terminative_mask"])
		regions_cmd.append(ter)
	


	t1t2 = ""
	if "t1_roi" in anacfg["method"] and tobool(anacfg["method"]["t1_roi"]) == True:
		if "t1" in subcfg["paths"]:
			t1t2 = " --t1t2=%s" % (os.path.abspath(os.path.join(
									subcfg["paths"]["base_dir"],
									subcfg["paths"]["t1_dir"],
									subcfg["paths"]["t1"])))
			regions_cmd.append(t1t2)
		else:
			raise KeyError("%s: No T1 specified in config" % (ps_id))
	elif "t2_roi" in anacfg["method"] and tobool(anacfg["method"]["t2_roi"]) == True:
		if "t2" in subcfg["paths"]:
			t1t2 = " --t1t2=%s" % (os.path.abspath(os.path.join(
									subcfg["paths"]["base_dir"],
									subcfg["paths"]["t2_dir"],
									subcfg["paths"]["t2"])))
			regions_cmd.append(t1t2)
		else:
			raise KeyError("%s: No T2 specified in config" % (ps_id))


	return regions_cmd



#subfunction of gen_DSISTUDIO_cmd, used by trk and ana actions
def gen_post_process_cmd(action, anacfg, subcfg):
	import os
	pp_cmd = []
	export = []

	if "actions" in anacfg["method"]["dsi_studio"]:
		if "export" in anacfg["method"]["dsi_studio"]["actions"][action]:#could be stat,tdi,tdi2,tdi_color,tdi2_color,report:fa:profilestyle:bandwidth
			export.append(" --export=")
			i=0
			for e in anacfg["method"]["dsi_studio"]["actions"][action]["export"]:
				i += 1
				if i == 1:
					export.append(e)
				else:
					export.append(",")
					export.append(e)
			export = "".join(export)
			pp_cmd.append(export)


			if "connectivity" in anacfg["method"]["dsi_studio"]["actions"][action]:#atlas connectivity matrix output
				cntvty = " -- connectivity=%s" % \
						 (anacfg["method"]["dsi_studio"]["actions"][action]["connectivity"])
				pp_cmd.append(cntvty)


			if "connectivity_type" in anacfg["method"]["dsi_studio"]["actions"][action]:#pass or end, default end
				cntvty_type = " --connectivity_type=%s" % \
							  (anacfg["method"]["dsi_studio"]["actions"][action]["connectivity_type"])
				pp_cmd.append(cntvty_type)


			if "connectivity_value" in anacfg["method"]["dsi_studio"]["actions"][action]:#count, ncount, mean_length, trk, fa, qa, adc, default count
				cntvty_value = " --connectivity_value=%s" % \
							   (anacfg["method"]["dsi_studio"]["actions"][action]["connectivity_value"])
				pp_cmd.append(cntvty_value)


			if "ref" in anacfg["method"]["dsi_studio"]["actions"][action]: #will output track coordinates based on T1w or T2w reference image
				if "T1w" == anacfg["method"]["dsi_studio"]["actions"][action]["ref"] and "t1" in subcfg["paths"]:
					ref = " --ref=%s" % \
						  os.path.abspath(os.path.join(subcfg["paths"]["base_dir"],
													   subcfg["paths"]["t1_dir"],
													   subcfg["paths"]["t1"]))
				elif "T2w" == anacfg["method"]["dsi_studio"]["actions"][action]["ref"] and "t2" in subcfg["paths"]:
					ref = " --ref=%s" % \
						  os.path.abspath(os.path.join(subcfg["paths"]["base_dir"],
													   subcfg["paths"]["t2_dir"],
													   subcfg["paths"]["t2"]))
				pp_cmd.append(ref)


	return pp_cmd


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
	sl = s.lower()
	if sl == True or sl == "true" or sl == "t" or sl == "y" or sl == "yes" or sl == "1" or sl == 1:
		return True
	elif sl == False or sl == "false" or sl == "f" or sl == "n" or sl == "no" or sl == "0" or sl == 0:
		return False
	else:
		print "Unexpected value for True/False"
		raise


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

def main():
	import nipype.pipeline.engine as pe
	from nipype.interfaces import fsl

	#Create BET node
	rbet = pe.Node(interface=fsl.BET(),name="rbet")
	rbet.inputs.in_file = ec_file
	rbet.inputs.out_file = be_file
	rbet.inputs.robust = True
	rbet.inputs.mask = True

	#Create EddyCorrect node
	eddyc = pe.Node(interface=fsl.EddyCorrect(),name="eddyc")
	eddyc.inputs.in_file = dti_file
	eddyc.inputs.out_file = ec_file
	eddyc.inputs.ref_num = 0
	

	#Create DSI studio tracking action nipype node
	DSITRK = Node(Function(input_names=["syscfgpath","anacfgpath","subcfgpath"],
				   output_names=["trk"],
				   function=DSI_TRK),
			  name='add_node')

	DSITRK.inputs.syscfg = os.environ["sys_config"]
	DSITRK.inputs.anacfg = os.environ["ana_config"]
	DSITRK.inputs.subcfg = os.environ["sub_config"]
