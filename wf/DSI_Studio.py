from nipype import Node, Function

import subprocess as sbp
import glob



#Create DSI studio tracking function
def DSI_TRK(syscfgpath, anacfgpath, subcfgpath,
	"""Run DSI studio tracking on command line
	
	Parameters
	----------
	anacfgpath : str (abspath to analysis config)
	subcfgpath : str (abspath to subject config)

	Outputs
	-------
	trk : .trk.gz file for each tract in anacfg, put in Regionsdir from
		subcfg
	"""
	
	import os

	#Get cfg json
	syscfg = read_config(syscfgpath)
	anacfg = read_config(anacfgpath)
	subcfg = read_config(subcfgpath)

	#Check if sub/scan is included in this group for analysis
	scanlist = anacfg["included_scans"]
	t_scanlist = frozenset(scanlist)
	sub_id = subcfg["sub_id"]
	scan_id = subcfg["scan_id"]
	t_sub_scan = frozenset([sub_id + "_" + scan_id])

	if not bool(t_scanlist.intersection(t_sub_scan)):
		print sub_id + "_" + scan_id + " SKIPPED - not part of Method"
		return

	#Get needed values from anacfg
	try:
		ana_id = anacfg["method"]
		opts = anacfg["track_opts"]
		for tract in anacfg["tracts"]:
			print tract
			#Make the commandline string to call DSI Studio
			TRKCALL = gen_cmd("trk", tract, anacfg, subcfg, opts)

			#Call DSI Studio
			if not TRKCALL: #False if empty
				subprocess.run(TRKCALL, check=True)
	except Exception:
		logger.exception("Error fiber tracking: " sub_id + "_" + scan_id)
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
def gen_cmd(action, tract, anacfg, subcfg, opts=None)
	
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
	logger = logging.getLogger(__name__)
	cmd = []
	if action == "trk":
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


		#set region options
		seed = "" #default is whole brain
		if "seed_mask" in anacfg["tracts"][tract]:
			seed = " --seed=" + os.path.abspath(os.path.join(subcfg["base_dir"], subcfg["dti_dir"], subcfg["regions_dir"],anacfg["tracts"][tract]["seed_mask"],".nii.gz"))


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
				rois = rois + " --roi" + str(num) + "=" + os.path.abspath(os.path.join(subcfg["base_dir"], subcfg["dti_dir"], subcfg["regions_dir"],roi,".nii.gz"))
				i = i + 1


		i = 1
		roas = ""
		if "exclusion_masks" in anacfg["tracts"][tract]:
			for roa in anacfg["tracts"][tract]["exclusion_masks"]:	
				if i == 1:
					num=""#first roa argument has no numeral
				else:
					num=i#further roa arguments go --roa2, --roa3
				roas = roas + " --roi" + str(num) + "=" + os.path.abspath(os.path.join(subcfg["base_dir"], subcfg["dti_dir"], subcfg["regions_dir"],roa,".nii.gz"))
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
				ends = ends + " --end" + str(num) + "=" + os.path.abspath(os.path.join(subcfg["base_dir"], subcfg["dti_dir"], subcfg["regions_dir"],end,".nii.gz"))
				i = i + 1


		ter = ""
		if "terminative_mask" in anacfg["tracts"][tract]:
			ter = " --ter=" + os.path.abspath(os.path.join(subcfg["base_dir"], subcfg["dti_dir"], subcfg["regions_dir"],anacfg["tracts"][tract]["terminative_mask"],".nii.gz"))

		#set required argument strings
		base = anacfg["dsi_studio_path"] +" --action=" + action
		source = " --source=" + os.path.abspath(os.path.join(subcfg["base_dir"], subcfg["dti_dir"], subcfg["fib_file"]))
		output = " --output=" + os.path.abspath(os.path.join(subcfg["base_dir"], subcfg["dti_dir"], subcfg["tracts_dir"], anacfg["method"])) + anacfg["tracts"][tract] + "trk.gz"

		cmd = [base, source, output, seed, rois, roas, ends, ter, t1t2, d.values()]

	
	if action == "ana":
		print "Working on this"

	else: #unrecognized action
		print action + ": gen cmd not yet implemented for action"
	return cmd


#Read config.json
def read_config(configpath):
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

