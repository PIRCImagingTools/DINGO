from nipype import IdentityInterface, Function
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
from nipype.interfaces.utility import Merge
import os
import glob
import re
import logging
from wf.utils import update_dict, read_config
from wf.DSI_Studio_base import (DSIStudioSource, DSIStudioReconstruct, 
								DSIStudioTrack, DSIStudioAnalysis)


#Create DSI Source Workflow - SRC file creation
def create_dsi_src(name="dsi_src", 
					parent_dir=None, sub_id=None, scan_id=None, uid=None,
					inputs_dict=None, **kwargs):
	"""Nipype node to create a src file in DSIStudio with dwi, bval, bvec
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'dsi_src')
	parent_dir	: 	Directory (default os.getcwd())
	sub_id		: 	Str
	scan_id		:	Str
	uid			:	Str
	inputs_dict	:	Dict (InputName=ParameterValue)
	**kwargs	:	InputName=ParameterValue
	
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
	if sub_id is not None:
		inputnode.inputs.sub_id = sub_id
	if scan_id is not None:
		inputnode.inputs.scan_id = scan_id
	if uid is not None:
		inputnode.inputs.uid = uid
		
	moddict=update_dict(indict=inputs_dict, **kwargs)
	
	if len(moddict) != 0:
		inputnode.inputs.inputs_dict = moddict

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
		interface=DSIStudioSource(indict=moddict))

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
	parent_dir=None, sub_id=None, scan_id=None, uid=None,
	inputMasksfx=None, inputs_dict=None, **kwargs):
	"""Nipype node to create a fib file in DSIStudio with src file
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'dsi_rec')
	grabFiles	: 	Bool (default True)
	parent_dir	: 	Directory 
	sub_id		: 	Str (default None)
	scan_id		:	Str (default None)
	uid			:	Str (default None)
	inputMasksfx:	Str (File suffix, default None)
		if None DSIStudio will mask automatically
	inputs_dict	:	Dict (InputName=ParameterValue)
	**kwargs	:	InputName=ParameterValue
	
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
	if sub_id is not None:
		inputnode.inputs.sub_id = sub_id
	if scan_id is not None:
		inputnode.inputs.scan_id = scan_id
	if uid is not None:
		inputnode.inputs.uid = uid
		
	moddict=update_dict(indict=inputs_dict, **kwargs)
	
	if len(moddict) != 0:
		inputnode.inputs.inputs_dict = moddict
		
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
	if inputMasksfx is not None:
		masktemplate=[]
		masktemplate.extend(("%s/%s/%s_%s_%s",inputMasksfx,".nii.gz"))
		datainnode.inputs.template.update(mask_file=''.join(masktemplate))
		datainnode.inputs.template_args.update(mask_file=[['sub_id',
			'scan_id','sub_id','scan_id','uid']])
	datainnode.inputs.sort_filelist=True
	
	#DSI Studio rec node
	recnode = pe.Node(
		name="recnode",
		interface=DSIStudioReconstruct(indict=moddict))
	
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
							
	
	if inputMasksfx is not None:
		recwf.connect([
			(datainnode, recnode, [("mask_file","mask")])
					])

	return recwf
	
	
def create_dsi_trk(name="dsi_trk",
	parent_dir=None, sub_id=None, scan_id=None, uid=None,
	inputs_dict=None, **kwargs):
	"""Nipype wf to create a trk with fiber file and input parameters
	
	Parameters
	----------
	name		: 	Str (workflow name, default 'dsi_trk')
	parent_dir	: 	Directory (default os.getcwd())
	sub_id		: 	Str (default None)
	scan_id		:	Str (default None)
	uid			:	Str (default None)
	inputs_dict	:	Dict (InputName=ParameterValue)
	**kwargs	:	InputName=ParameterValue
		any unspecified tracting parameters will be defaults of DSIStudiotract
	
	e.g. dsi_trk = create_dsi_trk(name='dsi_trk',
					parent_dir='/home/pirc/Desktop/DWI/CHD_tractography/CHP',
					sub_id='0004',
					scan_id='MR1',
					uid='DTIFIXED_ec')
					
	Returns
	-------
	trkwf		:	Nipype workflow
		trkwf.outputnode.outputs=['tract_list']
		e.g. '/home/pirc/Desktop/DWI/CHD_tractography/CHP/0004/MR1/
			  0004_MR1_DTIFIXED_ec.*.fib.gz'
	"""
	
	#Parse inputs
	inputnode = pe.Node(name="inputnode",
		interface=IdentityInterface(
			fields=[
				"parent_dir",
				"sub_id","scan_id","uid",
				"inputs_dict"],
			mandatory_inputs = True))
	if parent_dir is not None:
		inputnode.inputs.parent_dir = parent_dir
	if sub_id is not None:
		inputnode.inputs.sub_id = sub_id
	if scan_id is not None:
		inputnode.inputs.scan_id = scan_id
	if uid is not None:
		inputnode.inputs.uid = uid
	
	moddict=update_dict(indict=inputs_dict, **kwargs)
	
	if len(moddict) != 0:
		inputnode.inputs.inputs_dict = moddict
	
	#Data Grabber - get fib, regions by DSIStudiotract
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
		interface=DSIStudioTrack(indict=moddict))
	
	
	#Write Data done by DSI Studio
	#dataoutnode = pe.Node(
		#name="dataoutnode",
		#interface=nio.DataSink(
			#infields=[
				#"base_directory",
				#"container",
				#"container.scan",
				#"container.scan.tracts"]))
	
	#Join tracts into list per subject
	outputnode = pe.JoinNode(
		name="outputnode",
		interface=IdentityInterface(
			fields=["tract_list"]),
		joinsource="trknode",
		joinfield="tract_list")
		
	
	trkwf=pe.Workflow(name=name)
	trkwf.connect([
		(inputnode, datainnode, [("sub_id","sub_id"),
								("scan_id","scan_id"),
								("uid","uid")]),
		(datainnode, trknode, [("fib_file","source")]),
		(trknode, outputnode, [("tract","tract_list")])
				])
	return trkwf


def dsi_main():

	dsi_dir = os.environ["DSIDIR"]
	#anacfgpath = os.environ["ana_config"]
	anacfgpath = '/home/pirc/Desktop/DWI/CHD_test_analysis_config.json'
	anacfg = read_config(anacfgpath)

	#Check for included sub/scan list
	if "included_psids" in anacfg:
		scanlist = anacfg["included_psids"]
		t_scanlist = frozenset(scanlist)
	else:
		raise KeyError("included_psids not identified in analysis config")
	
	config_list = []

	for root,dirs,files in os.walk(anacfg["data_dir"]):
		for f in files:
			if re.search('config\.json(?!~)',f):
				potential = read_config(os.path.abspath(os.path.join(root,f)))
				try:
					pot_id = patient_scan(potential,True)
					t_pot_id = frozenset([pot_id])
					if bool(t_scanlist.intersection(t_pot_id)):
						print "%s: INCLUDED" % (pot_id)
						config_list.append(potential)
					else:
						print("%s: SKIPPED - does not match inclusion list" %
							(pot_id))
				except KeyError:#not a subject config file
					pass
	return config_list

