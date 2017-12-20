from nipype import Node, Function

import subprocess as sbp
import glob



#Create DSI studio tracking function
def DSI_TRK(syscfgpath, anacfgpath, subcfgpath,
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
	import logging

	#Get cfg json
	syscfg = read_config(syscfgpath)
	anacfg = read_config(anacfgpath)
	subcfg = read_config(subcfgpath)

	#Check if sub/scan is included in this group for analysis
	scanlist = anacfg["included_psids"]
	t_scanlist = frozenset(scanlist)
	pat_id = subcfg["pid"]
	scan_id = subcfg["scanid"]
	t_pat_scan = frozenset([pat_id + "_" + scan_id])

	if not bool(t_scanlist.intersection(t_sub_scan)):
		print pat_id + "_" + scan_id + " SKIPPED - not part of Method"
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
				subprocess.run(TRKCALL, check=True)
	except Exception:
		logger.exception("Error fiber tracking: " pat_id + "_" + scan_id)
		raise




	
#Create DSI studio tracking action nipype node
DSITRK = Node(Function(input_names=["syscfgpath","anacfgpath","subcfgpath"],
		       output_names=["trk"],
		       function=DSI_TRK),
	      name='add_node')

DSITRK.inputs.syscfg = os.environ['sys_config']
DSITRK.inputs.anacfg = os.environ['ana_config']
DSITRK.inputs.subcfg = os.environ['sub_config']

#Create command line string to run
def gen_DSISTUDIO_cmd(action, tract, syscfg, anacfg, subcfg, opts=None)
	
	"""Returns string to be called that will execute needed dsi_studio cmd
	
	Parameters
	----------
	action : str (3 letter action code)
	tract : str (tract identifier)
	anacfg : dict<json (contains method information, rois, roas, fa and 			        angle thresholds, dsi studio path)
	subcfg : dict<json (contains paths for input and output)
	opts : dict (changes to default arguments for action)
	"""		

	import os
	import numbers

	cmd = []
	base_cmd = syscfg["dsi_studio"]["path"] +" --action=" + action

	#Check relevant config file keys

	if "method" in anacfg:
		if "dsi_studio" in anacfg["method"]:
			if not "path" in syscfg["dsi_studio"]:
				print "DSI_Studio path unspecified"
				raise KeyError("syscfg:dsi_studio:path")
		else
			raise KeyError("anacfg:method:dsi_studio)
	else
		raise KeyError("anacfg:method")


	if not "psid" in subcfg:
		print "Patient/Scan ID unspecified"
		raise KeyError("subcfg:psid")


	if "paths" in subcfg:
		if not "dti" in subcfg["paths"]
			print "DTI directory unspecified"
			raise KeyError(subcfg["psid"]+":paths:dti")
	else
		raise KeyError(subcfg["psid"]+":paths")

	

	##### FIBER TRACKING ACTION #####
	if action == "trk":
		if not "tracts" in subcfg["paths"]
			print "Tract directory unspecified"
			raise KeyError(subcfg["psid"]+":paths:tracts")
		if not "fib_file" in subcfg["paths"]
			print "Fiber Tracking file unspecified"
			raise KeyError(subcfg["psid"]+":paths:fib_file")
		#set optional arguments defaults
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
		
		#update with parameters
		if not opts is None:
			for k in opts:
				if k in d:
					if isinstance(opts[k],str):
						d[k] = opts[k]
					elif isinstance(opts[k],numbers.Real):
						part = d[k].partition('=')
						d[k] = part[0]+part[1]+str(opts[k])



		#set required argument strings
		source_cmd = " --source=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["dti"], subcfg["paths"]["fib_file"]))

		output_cmd = " --output=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["dti"], subcfg["paths"]["tracts"], anacfg["method"]["name"])) + anacfg["tracts"][tract] + "trk.gz"

		regions_cmd = gen_regions_cmd(tract, anacfg, subcfg)

		post_process_cmd = gen_post_process_cmd(tract, anacfg, subcfg)

		cmd = [base_cmd, source_cmd, output_cmd, regions_cmd.values(), post_process_cmd.values(), d.values()]

	
	##### ANALYSIS ACTION #####
	elif action == "ana":
		print "Working on this"
		source_cmd = " --source=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["dti"], subcfg["paths"]["tracts"], anacfg["method"]["name"])) + anacfg["tracts"][tract] + "trk.gz"

		output_cmd = ""
		if "output" in anacfg["method"]["dsi_studio"]["commands"]["ana"] and not 2bool(anacfg["method"]["dsi_studio"]["commands"]["ana"]["output"]):
			output_cmd = " --output=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["dti"], subcfg["paths"]["tracts"], anacfg["method"]["name"])) + anacfg["tracts"][tract] + anacfg["method"]["dsi_studio"]["commands"]["ana"]["output"]
		
		regions_cmd = gen_regions_cmd(tract, anacfg, subcfg)

		post_process_cmd = gen_post_process_cmd(tract, anacfg, subcfg)
		
		cmd = [base_cmd, source_cmd, output_cmd, regions_cmd.values(), post-process_cmd.values()]

	else: #unrecognized action
		print action + ": gen cmd not yet implemented for action"
	return cmd




#subfunction of gen_DSISTUDIO_cmd, used by trk and ana actions
def gen_regions_cmd(tract, anacfg, subcfg)
	import os
	regions_cmd = {}
	
	if not "regions" in subcfg["paths"]:
		print "Regions directory unspecified"
		raise KeyError(subcfg["psid"]+":paths:regions")

	#set region options
	seed = "" #default is whole brain
	if "seed_mask" in anacfg["tracts"][tract]:
		seed = " --seed=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["dti"], subcfg["paths"]["regions"],anacfg["tracts"][tract]["seed_mask"],".nii.gz"))


	rois = ""
	i = 1
	if "inclusion_masks" in anacfg["tracts"][tract]:
		for roi in anacfg["tracts"][tract]["inclusion_masks"]:
			if i == 1:
				num=""#first roi argument has no numeral
			if i > 5:#cannot have more than 5 rois
				print "More than 5 rois detected, check analysis config file"
				break
			else:
				num=i#further roi arguments go --roi2, --roi3
			rois = rois + " --roi" + str(num) + "=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["dti"], subcfg["paths"]["regions"],roi,".nii.gz"))
			i = i + 1


	i = 1
	roas = ""
	if "exclusion_masks" in anacfg["tracts"][tract]:
		for roa in anacfg["tracts"][tract]["exclusion_masks"]:	
			if i == 1:
				num=""#first roa argument has no numeral
			else:
				num=i#further roa arguments go --roa2, --roa3
			roas = roas + " --roi" + str(num) + "=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["dti"], subcfg["paths"]["regions"],anacfg[roa,".nii.gz"))
			i = i + 1


	i = 1
	ends = ""
	if "ends_masks" in anacfg["tracts"][tract]:
		for end in anacfg["tracts"][tract]["ends"]
			if i == 1:
				num=""#first end argument has no numeral
			elif i > 2:#cannot have more than 2 ends
				print "More than 2 ends detected, check analysis config file"
				break
			else:
				num=i#second end argument is end2
			ends = ends + " --end" + str(num) + "=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["dti"], subcfg["paths"]["regions"],end,".nii.gz"))
			i = i + 1


	ter = ""
	if "terminative_mask" in anacfg["tracts"][tract]:
		ter = " --ter=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["dti"], subcfg["paths"]["regions"],anacfg["tracts"][tract]["terminative_mask"],".nii.gz"))



	t1t2 = ""
	if "t1_roi" in anacfg["method"] and 2bool(anacfg["method"]["t1_roi"]) == True:
		if "t1_dir" in subcfg["paths"]:
			t1t2 = "--t1t2=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["t1_dir"], subcfg["paths"]["t1_file"])
	elif "t2_roi" in anacfg["method"] and 2bool(anacfg["method"]["t1_roi"]) == True:
		if "t2_dir" in subcfg["paths"]:
			t1t2 = "--t1t2=" + os.path.abspath(os.path.join(subcfg["paths"]["base_dir"], subcfg["paths"]["t2_dir"], subcfg["paths"]["t2_file"])

	regions_cmd = dict(seed = seed,
			           rois = rois,
			           roas = roas,
			           ends = ends,
			           ter = ter,
			           t1t2 = t1t2)
	return regions_cmd


#subfunction of gen_DSISTUDIO_cmd, used by trk and ana actions
def gen_post_process_cmd(tract, anacfg, subcfg)
	import os
	pp_cmd = {}
    export = ""
    cntvty = ""
    cntvty_type = ""
    cntvty_value = ""
    cntvty_threshold = ""
    ref = ""

	if "commands" in anacfg["method"]["dsi_studio"]:
		for cmd in anacfg["method"]["dsi_studio"]["commands"]:
		    if "export" in anacfg["method"]["dsi_studio"]["commands"][cmd]:#could be stat,tdi,tdi2,tdi_color,tdi2_color,report:fa:profilestyle:bandwidth
			    export = " --export=" + anacfg["method"]["dsi_studio"]["commands"][cmd]["export"]

            if "connectivity" in anacfg["method"]["dsi_studio"]["commands"][cmd]:#atlas connectivity matrix output
                cntvty = " -- connectivity=" + anacfg["method"]["dsi_studio"]["commands"][cmd]["connectivity"]

            if "connectivity_type" in anacfg["method"]["dsi_studio"]["commands"][cmd]:#pass or end, default end
                cntvty_type = " --connectivity_type=" anacfg["method"]["dsi_studio"]["commands"][cmd]["connectivity_type"]

            if "connectivity_value" in anacfg["method"]["dsi_studio"]["commands"][cmd]:#count, ncount, mean_length, trk, fa, qa, adc, default count
                cntvty_value = " --connectivity_value=" anacfg["method"]["dsi_studio"]["commands"][cmd]["connectivity_value"]

            if "ref" in anacfg["method"]["dsi_studio"]["commands"][cmd]: #will output track coordinates based on T1w or T2w reference image
                if "T1w" == anacfg["method"]["dsi_studio"]["commands"][cmd]["ref"] and "t1" in subcfg["paths"]:
                    ref = os.path.abspath(os.path.join(subcfg["paths"]["base_dir"]["t1"]
                elif "T2w" == anacfg["method"]["dsi_studio"]["commands"][cmd]["ref"] and "t2" in subcfg["paths"]:
                    ref = os.path.abspath(os.path.join(subcfg["paths"]["base_dir"]["t2"]

    pp_cmd = dict(export = export,
                  connectivity = cntvty,
                  connectivity_type = cntvty_type,
                  connectivity_value = cntvty_value,
                  connectivity_threshold = cntvty_threshold,
                  ref = ref)
	return pp_cmd

#Convert str to boolean
def 2bool(s):
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

