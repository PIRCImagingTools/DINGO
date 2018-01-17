from nipype import IdentityInterface, Function
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
import os
import glob
import re
import logging
from wf.utils import *
from wf.DSI_Studio_base import *



#Create DSI Source Workflow - Fib file creation
def dsi_src(name="dsi_src", data_dir=None, scan_list=None):
	#Prepare inputs
	inputnode = pe.Node(name="inputnode",
						interface=IdentityInterface(fields=["data_dir",
															"scanid_list"]))
	if data_dir is not None:
		inputnode.inputs.data_dir = data_dir
	if scan_list is not None:
		#inputnode.inputs.scanid_list = scan_list
		inputnode.iterables=[("scanid_list", scan_list)]

	splitidnode = pe.Node(name="splitidnode",
							interface=Function(input_names=["psid","sep"],
								output_names=["subid","scanid","uid"],
								function=split_chpid))
#							iterfield=["psid"])
	splitidnode.inputs.sep = "_"

	#Select Files
	templates = {"dwi": "/{sub_id}/{scan_id}/{sub_id}_{scan_id}_{uid}.nii.gz",
				 "bvals":"/{sub_id}/{scan_id}/{sub_id}_{scan_id}_{uid}.bval",
				 "bvecs":"/{sub_id}/{scan_id}/{sub_id}_{scan_id}_{uid}.bvec"}
	datainnode = pe.Node(name="datainnode",
							interface=nio.SelectFiles(templates))
#							iterfield=["sub_id","scan_id","uid"])
	
	#Run DSI Studio SRC
	srcnode = pe.Node(name="srcnode",
						 interface=DSIStudioSource())
#						 iterfield=["source","bval","bvec"])

	#Write output
	dataoutnode = pe.Node(name="dataoutnode",
							interface=nio.DataSink(infields=["base_directory",
															"container",
															"container.scan",
															"uid"]))
#							iterfield=["base_directory",
#										"container",
#										"container.scan",
#										"uid"])

	srcwf=pe.Workflow(name=name)
	srcwf.connect([
		(inputnode, splitidnode, [("scanid_list","psid")]),
		(inputnode, datainnode, [("data_dir","base_directory")]),
		(splitidnode, datainnode, [("subid","sub_id"),
									("scanid","scan_id"),
									("uid","uid")]),
		(datainnode, srcnode, [("dwi","source"),
								("bvals","bval"),
								("bvecs","bvec")]),
		(inputnode, dataoutnode, [("data_dir","base_directory")]),
		(splitidnode, dataoutnode, [("subid", "container"),
									("scanid","container.scan"),
									("uid","uid")]),
		(srcnode, dataoutnode, [("output","container.scan.@src_file")])
				])
	return srcwf


def dsi_rec(name="dsi_rec", data_dir=None, scan_list=None):
	#Parse inputs
	inputnode = pe.Node(name="inputnode",
						interface=IdentityInterface(fields=["data_dir",
															"scanid_list"]))
	if data_dir is not None:
		inputnode.inputs.data_dir = data_dir
	if scan_list is not None:
		inputnode.inputs.scanid_list = scan_list

	splitidnode = pe.Node(name="splitidnode",
					   interface=Function(input_names=["scanid_list","sep"],
							   output_names=["subid","scanid","uid"],
							   function=split_chpid))
	splitidnode.inputs.sep = "_"

	recwf=pe.Workflow(name=name)
	recwf.connect([
		(inputnode, splitidnode, [("scanid_list","psid")])
				])
	return recwf


def dsi_main():

	syscfgpath = os.environ["sys_config"]
	anacfgpath = os.environ["ana_config"]
	

	syscfg = read_config(syscfgpath)
	anacfg = read_config(anacfgpath)

	#Check for included sub/scan list
	if "included_psids" in anacfg:
		scanlist = anacfg["included_psids"]
		t_scanlist = frozenset(scanlist)
	else:
		raise KeyError("included_psids not identified in analysis config")

	for root,dirs,files in os.walk(anacfg["data_dir"]):
		for f in files:
			if re.search('config\.json(?!~)',f):
				potential = read_config(os.path.abspath(os.path.join(root,f)))
				try:
					pot_id = patient_scan(potential,True)
					t_pot_id = frozenset([pot_id])
					if bool(t_scanlist.intersection(t_pot_id)):
						print "%s: INCLUDED" % (pot_id)
						subcfg = potential
					else:
						print "%s: SKIPPED - does not match inclusion list" % (pot_id)
				except KeyError:#not a subject config file
					pass

