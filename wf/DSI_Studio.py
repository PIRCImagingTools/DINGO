from nipype import Node, Function, MapNode, Workflow
#import nipype.pipeline.engine as pe
import os
import glob
from utils import *



#Create DSI studio tracking function
def dsi_studio(action, syscfg, anacfg, subcfg):
	"""Run DSI studio tracking on command line
	
	Parameters
	----------
	action : str (DSI Studio command to execute)
	syscfg : dict<json (system config paths)
	anacfg : dict<json (contains method information, rois, roas, fa and angle
		thresholds, dsi studio path)
	subcfg : dict<json (contains paths for input and output)

	Outputs
	-------
	various depending on action and export listed in analysis config
	"""
	
	import subprocess
	import logging

	logger = logging.getLogger(__name__)

	ps_id = patient_scan(subcfg)
	#Get needed values from anacfg
	try:
		ana_id = anacfg["method"]["name"]
		if "track_opts" in anacfg["method"]["actions"]["trk"]:
			opts = anacfg["track_opts"]
		for tract in anacfg["tracts"]:
			print tract
			#Make the commandline string to call DSI Studio
			logger.info("Generating DSI Studio command for %s:%s:%s" % 
						(ana_id,ps_id,action))
			DSICALL = gen_dsistudio_cmd(action, tract, anacfg, subcfg)

			#Call DSI Studio
			if not DSICALL: #False if empty
				logger.info("Launching DSI Studio for %s:%s:%s" % 
							(ana_id,ps_id,action))
				subprocess.call(TRKCALL)
	except Exception:
		logger.exception("Error running DSI Studio: %s:%s:%s" % 
						(ana_id,ps_id,action))
		raise


def map_dsi_studio(tracts,action,syscfg,anacfg,subcfg)
	import subprocess
	import logging



#Create command line string to run
def gen_dsistudio_cmd(action, tract, syscfg, anacfg, subcfg):
	
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
	"""Generate regions portion of dsi studio trk and ana actions

	Parameters
	----------
	tract : str (name of tract, e.g. CCBody, CST_L)
	anacfg : dict<json (contains method information, rois, roas, fa and angle
		thresholds, dsi studio path)
	subcfg : dict<json (contains paths for input and output)

	Returns
	-------
	List of region commands
	"""
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
	"""Generate post processing portion of dsi studio trk and ana actions

	Parameters
	----------
	action : str (id of dsi studio action, e.g. trk, ana)
	anacfg : dict<json (contains method information, rois, roas, fa and angle
		thresholds, dsi studio path)
	subcfg : dict<json (contains paths for input and output)

	Returns
	-------
	List of post process commands
	"""
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



def dsi_main():
	import nipype.pipeline.engine as pe
	import os
	import logging
	from utils import *

	syscfgpath = os.environ["sys_config"]
	anacfgpath = os.environ["ana_config"]
	subcfgpath = os.environ["sub_config"]

	syscfg = read_config(syscfgpath)
	anacfg = read_config(anacfgpath)

	#Check for included sub/scan list
	if "included_psids" in anacfg:
		scanlist = anacfg["included_psids"]
		t_scanlist = frozenset(scanlist)
	else:
		raise KeyError("included_psids not identified in analysis config")

	for ss in scanlist:
		
	
	subcfg = read_config(subcfgpath)
	ss_id = patient_scan(subcfg)
	t_sub_scan = frozenset([ss_id])
	if not bool(t_scanlist.intersection(t_sub_scan)):
		print "%s: SKIPPED - not part of Method" % (ss_id)
		return

	#Create DSI studio tracking action nipype node
	DSITRK = Node(Function(input_names=["action","syscfg","anacfg","subcfg"],
						   output_names=["trk"],
						   function=dsi_studio),
				  name="dsi_trk")

	DSITRK.inputs.action = "trk"
	DSITRK.inputs.syscfg = syscfg
	DSITRK.inputs.anacfg = anacfg
	DSITRK.inputs.subcfg = subcfg

#	DSITRK = MapNode(Function(input_names=["action","syscfg","anacfg","subcfg"],
#								output_names=["trk_list"],
#								function=dsi_studio),
#					name="map_dsi_trk",
#					iterfield=["tracts"])
#	DSITRK.inputs.action = "trk"
#	DSITRK.inputs.syscfg = syscfg
#	DSITRK.inputs.anacfg = anacfg
#	DSITRK.inputs.subcfg = subcfg


	#Create DSI studio analysis action nipype node
	DSIANA = Node(Function(input_names=["action","syscfg","anacfg","subcfg"],
						   output_names=["stats"],
						   function=dsi_studio),
				  name="dsi_ana")

	DSIANA.inputs.action = "ana"
	DSIANA.inputs.syscfg = syscfg
	DSIANA.inputs.anacfg = anacfg
	DSIANA.inputs.subcfg = subcfg


	#Connect trk and ana
	DSITA = Workflow(name="DSITA")
	DSITA.base_dir = anacfg["data_dir"]
	DSITA.connect([
					(DSITRK, DSIANA, [
				  ])
					
