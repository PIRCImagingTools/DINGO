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
def create_dsi_src(name="dsi_src", data_dir=None, scan_list=None):
	#Prepare inputs
	inputnode = pe.Node(name="inputnode",
						interface=IdentityInterface(fields=["data_dir",
															"scanid_list"]))
	if data_dir is not None:
		inputnode.inputs.data_dir = data_dir
	else:
		inputnode.inputs.data_dir = os.getcwd()
	if scan_list is not None:
		#inputnode.inputs.scanid_list = scan_list
		inputnode.iterables=("scanid_list", scan_list)

	splitidnode = pe.Node(name="splitidnode",
						interface=Function(input_names=["psid","sep"],
								output_names=["subid","scanid","uid"],
								function=split_chpid))
#							iterfield=["psid"])
	splitidnode.inputs.sep = "_"

	#Select Files - Does not seem as configurable after init
#	templates = {"dwi": "{subid}/{scanid}/{subid}_{scanid}_{uid}.nii.gz",
#				 "bval":"{subid}/{scanid}/{subid}_{scanid}_{uid}.bval",
#				 "bvec":"{subid}/{scanid}/{subid}_{scanid}_{uid}.bvec"}
#	datainnode = pe.Node(name="datainnode",
#							interface=nio.SelectFiles(templates))
#							iterfield=["sub_id","scan_id","uid"])

	#DataGrabber - get dwi,bval,bvec
	datainnode = pe.Node(name="datainnode",
		interface=nio.DataGrabber(infields=['subid','scanid',
											'subid','scanid','uid'],
								outfields=['dwi','bval','bvec']))
	datainnode.inputs.base_directory = inputnode.inputs.data_dir
	#template = subid/scanid/subid_scanid_uid.nii.gz
	datainnode.inputs.template = "%s/%s/%s_%s_%s.nii.gz"
	datainnode.inputs.field_template = dict(
		dwi="%s/%s/%s_%s_%s.nii.gz",
		bval="%s/%s/%s_%s_%s.bval",
		bvec="%s/%s/%s_%s_%s.bvec")
	datainnode.inputs.template_args = dict(
		dwi=[['subid','scanid','subid','scanid','uid']],
		bval=[['subid','scanid','subid','scanid','uid']],
		bvec=[['subid','scanid','subid','scanid','uid']])
	datainnode.inputs.sort_filelist=True
	
	
	#DSI Studio SRC node
	srcnode = pe.Node(name="srcnode",
						 interface=DSIStudioSource())
#						 iterfield=["source","bval","bvec"])

	#Write output
	dataoutnode = pe.Node(name="dataoutnode",
						interface=nio.DataSink(infields=["base_directory",
														"container",
														"container.scan",
														"uid"]))
#						iterfield=["base_directory",
#									"container",
#									"container.scan",
#									"uid"])

	outputnode = pe.Node(name="outputnode",
						interface=IdentityInterface(fields=["src_file"]))

	#Create source file workflow
	srcwf=pe.Workflow(name=name)
	srcwf.connect([
		(inputnode, splitidnode, [("scanid_list","psid")]),
		(inputnode, datainnode, [("data_dir","base_directory")]),
		(splitidnode, datainnode, [("subid","subid"),
									("scanid","scanid"),
									("uid","uid")]),
		(datainnode, srcnode, [("dwi","source"),
								("bval","bval"),
								("bvec","bvec")]),
		(inputnode, dataoutnode, [("data_dir","base_directory")]),
		(splitidnode, dataoutnode, [("subid", "container"),
									("scanid","container.scan"),
									("uid","uid")]),
		(srcnode, dataoutnode, [("output","container.scan.@src_file")]),
		(srcnode, outputnode, [("output","src_file")])
				])
	return srcwf


def create_dsi_rec(name="dsi_rec", data_dir=None, scan_list=None, 
					inputmask=False):
	#Parse inputs
	inputnode = pe.Node(name="inputnode",
						interface=IdentityInterface(fields=["data_dir",
															"scanid_list"]))
	if data_dir is not None:
		inputnode.inputs.data_dir = data_dir
	if scan_list is not None:
		inputnode.iterables=("scanid_list", scan_list)

	splitidnode = pe.Node(name="splitidnode",
					   interface=Function(input_names=["psid","sep"],
							   output_names=["subid","scanid","uid"],
							   function=split_chpid))
	splitidnode.inputs.sep = "_"
	
	#Data Grabber - Get src
	datainnode = pe.Node(name="datainnode",
		interface=nio.DataGrabber(infields=['subid','scanid',
											'subid','scanid','uid'],
								outfields=['src_file']))
	datainnode.inputs.base_directory = inputnode.inputs.data_dir
	#template = subid/scanid/subid_scanid_uid.src.gz
	datainnode.inputs.template = "%s/%s/%s_%s_%s.src.gz"
	datainnode.inputs.field_template = dict(
		src_file="%s/%s/%s_%s_%s.fib.gz")
	datainnode.inputs.template_args = dict(
		src_file=[['subid','scanid','subid','scanid','uid']])
	datainnode.inputs.sort_filelist=True
	
	#DSI Studio rec node
	recnode = pe.Node(name="recnode",
						interface=DSIStudioReconstruct())
	
	#Write output
	dataoutnode = pe.Node(name="dataoutnode",
						interface=nio.DataSink(infields=["base_directory",
														"container",
														"container.scan",
														"uid"]))
	outputnode = pe.Node(name="outputnode",
						interface=IdentityInterface(fields=["fib_file"]))
	
	#Create reconstruct workflow
	recwf=pe.Workflow(name=name)
	recwf.connect([
		(inputnode, splitidnode, [("scanid_list","psid")]),
		(splitidnode, datainnode, [("subid","subid"),
									("scanid","scanid"),
									("uid","uid")]),
		(datainnode, recnode, [("src_file","source")]),
		(inputnode, dataoutnode, [("data_dir","base_directory")]),
		(splitidnode, dataoutnode, [("subid", "container"),
									("scanid","container.scan"),
									("uid","uid")]),
		(recnode, dataoutnode, [("fiber_file","container.scan.@fib_file")]),
		(recnode, outputnode, [("fiber_file","fib_file")])
				])
	return recwf
	
	
def create_dsi_trk(name="dsi_trk", data_dir=None, scan_list=None, 
	seed_list=None, roi_list=None, roa_list=None, end_list=None, ter_list=None):
	
	#Parse inputs
	inputnode = pe.Node(name="inputnode",
		interface=IdentityInterface(fields=["data_dir","scanid_list",
											"seed_list","roi_list","roa_list",
											"end_list","ter_list"]))
	if data_dir is not None:
		inputnode.inputs.data_dir = data_dir
	inputiters = []
	if scan_list is not None:
		inputiters.append(("scanid_list", scan_list))
	if seed_list is not None:
		inputiters.append(("seed_list", seed_list))
	if roi_list is not None:
		inputiters.append(("roi_list", roi_list))
	if roa_list is not None:
		inputiters.append(("roa_list", roa_list))
	if end_list is not None:
		inputiters.append(("end_list", end_list))
	if ter_list is not None:
		inputiters.append(("ter_list", ter_list))
	if inputiters:
		inputnode.iterables = inputiters

	splitidnode = pe.Node(name="splitidnode",
					   interface=Function(input_names=["psid","sep"],
							   output_names=["subid","scanid","uid"],
							   function=split_chpid))
	splitidnode.inputs.sep = "_"
	
	#Data Grabber - get fib, regions
	datainnode = pe.Node(name="datainnode",
						interface=nio.DataGrabber(infields=['subid','scanid',
													'subid','scanid','uid'],
												outfields=[""]))
	datainnode.inputs.base_directory = inputnode.inputs.data_dir
	#template = subid/scanid/subid_scanid_uid.fib.gz
	datainnode.inputs.template = "%s/%s/%s_%s_%s.fib.gz"
	datainnode.inputs.field_template = dict(
		src_file="%s/%s/%s_%s_%s.fib.gz")
	datainnode.inputs.template_args = dict(
		src_file=[['subid','scanid','subid','scanid','uid']])
	datainnode.inputs.sort_filelist=True
	
	
	trkwf=pe.Workflow(name=name)
	trkwf.connect([
		(inputnode, splitidnode, [("scanid_list","psid")]),
		(splitidnode, datainnode, [("subid","subid"),
									("scanid","scanid"),
									("uid","uid")]),
				])
	return trkwf


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
						print("%s: SKIPPED - does not match inclusion list" %
							(pot_id))
				except KeyError:#not a subject config file
					pass

