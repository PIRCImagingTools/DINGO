from nipype import IdentityInterface, Function
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
from nipype.interfaces.utility import Merge
import os
import glob
import re
import logging
from wf.utils import *
from wf.DSI_Studio_base import (DSIStudioSource, DSIStudioReconstruct, 
								DSIStudioTrack, DSIStudioAnalysis)


def create_split_ids(name="split_ids", sep=None,
					parent_dir=None, scan_list=None):
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
		(inputnode, splitidsnode, [("scan_list", "psid")]),
		(inputnode, outputnode, [("parent_dir", "parent_dir")]),
		(splitidsnode, outputnode, [("sub_id", "sub_id"),
									("scan_id", "scan_id"),
									("uid", "uid")])
					])
	return splitids


#Create DSI Source Workflow - SRC file creation
def create_dsi_src(name="dsi_src", 
					parent_dir=None, sub_id=None, scan_id=None, uid=None):
	"""Nipype node to create a src file in DSIStudio with dwi, bval, bvec
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'dsi_src')
	grabFiles	: 	Bool (default True)
	parent_dir	: 	Directory (default os.getcwd())
	sub_id		: 	Str
	scan_id		:	Str
	uid			:	Str
	
	e.g. dsi_src = create_dsi_src(name='dsi_src',
					grabFiles=True,
					parent_dir='/home/pirc/Desktop/DWI/CHD_tractography/CHP',
					sub_id='0004',
					scan_id='MR1',
					uid='DTIFIXED_ec')
					
	Returns
	-------
	srcwf		:	Nipype workflow
		srcwf.outputnode.outputs=['src_file']
		e.g. '/home/pirc/Desktop/DWI/CHD_tractography/CHP/0004/MR1/
			  0004_MR1_DTIFIXED_ec.src.gz'
	"""
	
	#Prepare inputs
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
		inputnode.inputs.parent_dir = parent_dir
	else:
		inputnode.inputs.parent_dir = os.getcwd()
	if sub_id is not None:
		inputnode.inputs.sub_id = sub_id
	if scan_id is not None:
		inputnode.inputs.scan_id = scan_id
	if uid is not None:
		inputnode.inputs.uid = uid

	#Select Files - Does not seem as configurable after init
#	templates = {"dwi": "{subid}/{scanid}/{subid}_{scanid}_{uid}.nii.gz",
#				 "bval":"{subid}/{scanid}/{subid}_{scanid}_{uid}.bval",
#				 "bvec":"{subid}/{scanid}/{subid}_{scanid}_{uid}.bvec"}
#	datainnode = pe.Node(
#		name="datainnode",
#		interface=nio.SelectFiles(templates))
	
	#DataGrabber - get dwi,bval,bvec
	datainnode = pe.Node(
		name="datainnode",
		interface=nio.DataGrabber(
			infields=[
				'sub_id',
				'scan_id',
				'uid'],
			outfields=[
				'dwi',
				'bval',
				'bvec']))
	#datainnode.inputs.base_directory = inputnode.inputs.parent_dir
	#template = subid/scanid/subid_scanid_uid.nii.gz
	datainnode.inputs.template = "%s/%s/%s_%s_%s.nii.gz"
	datainnode.inputs.field_template = dict(
		dwi="%s/%s/%s_%s_%s_ec.nii.gz",
		bval="%s/%s/%s_%s_%s.bval",
		bvec="%s/%s/%s_%s_%s.bvec")
	datainnode.inputs.template_args = dict(
		dwi=[['sub_id','scan_id','sub_id','scan_id','uid']],
		bval=[['sub_id','scan_id','sub_id','scan_id','uid']],
		bvec=[['sub_id','scan_id','sub_id','scan_id','uid']])
	datainnode.inputs.sort_filelist=True

	#DSI Studio SRC node
	srcnode = pe.Node(
		name="srcnode",
		interface=DSIStudioSource())

	#Write output done by DSI Studio

	#Make output available to not data grabber workflows
	outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(fields=[
			"parent_dir",
			"src_file"]))

	#Create source file workflow
	srcwf=pe.Workflow(name=name)
	
	#Connect basic workflow
	srcwf.connect([
		(inputnode, datainnode, [("parent_dir","base_directory"),
								("sub_id", "sub_id"),
								("scan_id", "scan_id"),
								("uid", "uid")]),
		(datainnode, srcnode, [("dwi","source"),
								("bval","bval"),
								("bvec","bvec")]),
		(srcnode, outputnode, [("output","src_file")])
				])
		
	return srcwf


#Create DSI rec workflow - FIB file creation
def create_dsi_rec(name="dsi_rec", 
	inputMask=None,
	parent_dir=None, sub_id=None, scan_id=None, uid=None):
	"""Nipype node to create a fib file in DSIStudio with src file
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'dsi_rec')
	grabFiles	: 	Bool (default True)
	inputMask	:	Str (File suffix, default None)
		if None DSIStudio will mask automatically
	parent_dir	: 	Directory (default os.getcwd())
	sub_id		: 	Str (default None)
	scan_id		:	Str (default None)
	uid			:	Str (default None)
	
	e.g. dsi_rec = create_dsi_rec(name='dsi_rec',
					grabFiles=True,
					inputMask='_be_mask_edited'
					parent_dir='/home/pirc/Desktop/DWI/CHD_tractography/CHP',
					sub_id='0004',
					scan_id='MR1',
					uid='DTIFIXED_ec')
					
	Returns
	-------
	recwf		:	Nipype workflow
		recwf.outputnode.outputs=['fib_file']
		e.g. '/home/pirc/Desktop/DWI/CHD_tractography/CHP/0004/MR1/
			  0004_MR1_DTIFIXED_ec.*.fib.gz'
	"""
	#Prepare inputs
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
		inputnode.inputs.parent_dir = parent_dir
	else:
		inputnode.inputs.parent_dir = os.getcwd()
	if sub_id is not None:
		inputnode.inputs.sub_id = sub_id
	if scan_id is not None:
		inputnode.inputs.scan_id = scan_id
	if uid is not None:
		inputnode.inputs.uid = uid
		
	#Data Grabber - Get src
	datainnode = pe.Node(
		name="datainnode",
		interface=nio.DataGrabber(infields=['sub_id','scan_id',
											'sub_id','scan_id','uid'],
								outfields=['src_file']))
	#datainnode.inputs.base_directory = inputnode.inputs.parent_dir
	#template = subid/scanid/subid_scanid_uid.src.gz
	datainnode.inputs.template = "%s/%s/%s_%s_%s.nii.gz"
	datainnode.inputs.field_template = dict(
		src_file="%s/%s/%s_%s_%s.src.gz")
	datainnode.inputs.template_args = dict(
		src_file=[['sub_id','scan_id','sub_id','scan_id','uid']])
	#grab mask if suffix is provided
	if inputMask is not None:
		masktemplate=[]
		masktemplate.extend(("%s/%s/%s_%s_%s",inputMask,".nii.gz"))
		datainnode.inputs.template.update(mask_file=''.join(masktemplate))
		datainnode.inputs.template_args.update(mask_file=[['sub_id',
			'scan_id','sub_id','scan_id','uid']])
		recwf.connect([(datainnode, recnode, [("mask_file","mask")])])
	datainnode.inputs.sort_filelist=True
	
	#DSI Studio rec node
	recnode = pe.Node(
		name="recnode",
		interface=DSIStudioReconstruct())
	
	#Write output done by DSI Studio
	
	#Make output available to non datagrabber workflows
	outputnode = pe.Node(
		name="outputnode",
		interface=IdentityInterface(
			fields=["fib_file"]))
	
	#Create reconstruct workflow
	recwf=pe.Workflow(name=name)
	recwf.connect([
		(inputnode, datainnode, [("sub_id","sub_id"),
								("scan_id","scan_id"),
								("uid","uid")]),
		(datainnode, recnode, [("src_file","source")]),
		(recnode, outputnode, [("fiber_file","fib_file")])
				])
							
	
	if inputMask is not None:
		recwf.connect([
			(datainnode, recnode, [("mask_file","mask")])
					])

	return recwf
	
	
def create_dsi_trk(name="dsi_trk",
	parent_dir=None, sub_id=None, scan_id=None, uid=None,
	seed=None, roi_list=None, roa_list=None, end_list=None, ter=None):
	"""Nipype node to create a trk files in DSIStudio with fib, and region files
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'dsi_trk')
	grabFiles	: 	Bool (default True)
	parent_dir	: 	Directory (default os.getcwd())
	sub_id		: 	Str (default None)
	scan_id		:	Str (default None)
	uid			:	Str (default None)
	seed		:	List[File]
	roi_list	:	List[File]
	roa_list	:	List[File]
	end_list	:	List[File]
	ter_list	:	List[File]
	
	e.g. dsi_rec = create_dsi_rec(name='dsi_rec',
					grabFiles=True,
					inputMask='_be_mask_edited'
					parent_dir='/home/pirc/Desktop/DWI/CHD_tractography/CHP',
					sub_id='0004',
					scan_id='MR1',
					uid='DTIFIXED_ec')
					
	Returns
	-------
	recwf		:	Nipype workflow
		recwf.outputnode.outputs=['fib_file']
		e.g. '/home/pirc/Desktop/DWI/CHD_tractography/CHP/0004/MR1/
			  0004_MR1_DTIFIXED_ec.*.fib.gz'
	"""
	
	#Parse inputs
	inputnode = pe.Node(name="inputnode",
		interface=IdentityInterface(
			fields=[
				"parent_dir",
				"sub_id","scan_id","uid",
				"seed","roi_list","roa_list","end_list","ter"]))
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
	if seed is not None:
		inputnode.inputs.seed = seed
	if ter is not None:
		inputnode.inputs.ter = ter
		
	inputiters = []
	if scan_list is not None:
		inputiters.append(("scanid_list", scan_list))
	if roi_list is not None:
		inputiters.append(("roi_list", roi_list))
	if roa_list is not None:
		inputiters.append(("roa_list", roa_list))
	if end_list is not None:
		inputiters.append(("end_list", end_list))
	if inputiters:
		inputnode.iterables = inputiters
	
	#Data Grabber - get fib, regions
	datainnode = pe.Node(
		name="datainnode",
		interface=nio.DataGrabber(
			infields=['subid','scanid','subid','scanid','uid'],
			outfields=[""]))
	datainnode.inputs.base_directory = inputnode.inputs.data_dir
	#template = subid/scanid/subid_scanid_uid.fib.gz
	datainnode.inputs.template = "%s/%s/%s_%s_%s.fib.gz"
	datainnode.inputs.field_template = dict(
		fib_file="%s/%s/%s_%s_%s.fib.gz")
	datainnode.inputs.template_args = dict(
		fib_file=[['sub_id','scan_id','sub_id','scan_id','uid']])
	datainnode.inputs.sort_filelist=True
	
	#DSI TRK
	trknode = pe.Node(
		name="trknode",
		interface=DSIStudioTrack())
	
	#Write Data
	dataoutnode = pe.Node(
		name="dataoutnode",
		interface=nio.DataSink(
			infields=[
				"base_directory",
				"container",
				"container.scan",
				"container.scan.tracts")
	
	#Join tracks into list per subject
	outputnode = pe.JoinNode(
		name="outputnode",
		interface=IdentityInterface(
			fields=["track_list"]),
		joinsource="trknode",
		joinfield="track_list")
		
	
	trkwf=pe.Workflow(name=name)
	trkwf.connect([
		(inputnode, datainnode, [("sub_id","sub_id"),
								("scan_id","scan_id"),
								("uid","uid")]),
		(datainnode, trknode, [("fib_file","source")]),
				])
	return trkwf


def dsi_main():

	dsi_dir = os.environ["DSIDIR"]
	anacfgpath = os.environ["PATH"]["ana_config"]
	

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

