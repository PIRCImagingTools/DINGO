import os
from nipype import config, logging
from DINGO.utils import (DynImport, read_config, split_chpid,
						join_strs, add_id_subs, fileout_util)
from DINGO.base import DINGO, DINGOflow, DINGOnode
from nipype import IdentityInterface, SelectFiles, Function
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio

#config.enable_debug_mode()
#logging.update_logging(config)

	
class HelperFlow(DINGO):
	
	def __init__(self, **kwargs):
		wfm = {
		'SplitIDs'				:	'DINGO.wf',
		'FileIn'				:	'DINGO.wf',
		'FileOut'				:	'DINGO.wf'
		}
		
		super(HelperFlow, self).__init__(workflow_to_module=wfm, **kwargs)
	
	
class SplitIDs(DINGOflow):
	_inputnode = 'inputnode'
	_outputnode = 'outputnode'
	
	def __init__(self, name='SplitIDs',\
	inputs={'parent_dir':None,'scan_list':None,'scan_list_sep':'_'}, **kwargs):
		"""Nipype node to iterate a list of ids into separate subject, scan, and
		task ids.
		
		Parameters
		----------
		name			:	Str (workflow name, default 'split_ids')
		parent_dir		:	Directory (contains subject folders)
		scan_list		:	List[Str] 
		scan_list_sep	:	Str (separator for fields in id)
			
		e.g. split_ids = create_split_ids(name='split_ids', 
					parent_dir=os.getcwd(),
					scan_list=[0761_MR1_42D_DTIFIXED,CHD_052_01a_DTIFIXED],
					sep='_')
			
		Returns
		-------
		splitids	:	Nipype workflow
		(splitids.outputnode.outputs=['sub_id','scan_id','uid'])
		e.g. {0: {parent_dir='/home/pirc/Desktop/DWI/CHD_tractography/CHP',
					sub_id='0761', scan_id='MR1', uid='42D_DTIFIXED'},
			  1: {parent_dir='/home/pirc/Desktop/DWI/CHD_tractography/CHP',
					sub_id='CHD_052', scan_id='01a', uid='DTIFIXED'}}
					
		Workflow Inputs
		---------------
		inputnode.scan_list
		inputnode.scan_list_sep
		
		Workflow Outputs
		----------------
		outputnode.sub_id
		outputnode.scan_id
		outputnode.uid
		"""
		super(SplitIDs, self).__init__(name=name, **kwargs)
		
		#Create Workflow
		splitids = pe.Workflow(name=name)
		if 'parent_dir' in inputs and inputs['parent_dir'] is not None:
			self.base_dir = inputs['parent_dir']
		
		inputnode = pe.Node(
			name="inputnode",
			interface=IdentityInterface(
				fields=[
					"scan_list",
					"scan_list_sep"],
				mandatory_inputs=True))
		if 'scan_list' in inputs and inputs['scan_list'] is not None:
			if isinstance(inputs['scan_list'], list):
				inputnode.inputs.scan_list = inputs['scan_list']
			elif isinstance(inputs['scan_list'], str):
				inputnode.inputs.scan_list = [inputs['scan_list']]
			inputnode.iterables = ("scan_list", inputnode.inputs.scan_list)
		else:
			print("%s.inputnode.scan_list must be set before running" % name)
			
		if 'scan_list_sep' in inputs and inputs['scan_list_sep'] is not None:
			inputnode.inputs.scan_list_sep = inputs['scan_list_sep']
		else:
			print("%s.inputnode.scan_list_sep must be set before running" % 
				name)

		splitidsnode = pe.Node(
			name="splitidsnode",
			interface=Function(
				input_names=["psid","sep"],
				output_names=["sub_id","scan_id","uid"],
				function=split_chpid))
			
		outputnode = pe.Node(
			name="outputnode",
			interface=IdentityInterface(
				fields=["sub_id",
						"scan_id",
						"uid"],
				mandatory_inputs=True))
				
		#Connect workflow
		self.connect([
			(inputnode, splitidsnode, 
				[("scan_list", "psid"),
				("scan_list_sep","sep")]),
			(splitidsnode, outputnode, 
				[("sub_id", "sub_id"),
				("scan_id", "scan_id"),
				("uid", "uid")])
			])
	
	
class FileIn(DINGOnode):
	#_inputnode = 'filein'
	#_outputnode = 'filein'

	connection_spec = {
		'sub_id'			:	['SplitIDs','sub_id'],
		'scan_id'			:	['SplitIDs','scan_id'],
		'uid'				:	['SplitIDs','uid']
	}
	
	def __init__(self, name='FileIn_SubScanUID',\
	inputs={'infields':None, 'outfields':None, 'exts':None, 'template':None,\
	'field_template':None, 'template_args':None, 'sort_filelist':True},\
	**kwargs):
		"""
		Parameters
		----------
		name			:	Workflow name
		infields		:	List, template field arguments
			(default ['sub_id','scan_id','uid'])
		outfields		:	List, output files 
			(default ['nifti'])
		exts			:	Dict, extensions for output files
			(default {'nifti':'.nii.gz'}, only used if field_template 
			unspecified for outfield, and template ends in .ext)
		template		:	Str, default template
			(default '%s/%s/%s_%s_%s.ext')
		field_template	:	Dict, overwrite default template per outfield
		template_args	:	Dict, linking infields to template or field_template
		sort_filelist	:	Boolean
		
		Returns
		-------
		DataGrabber workflow
		
		Inputs
		------
		filein.infields
		filein.template
		filein.field_template
		filein.template_args
		filein.sort_filelist
		filein.base_directory
		
		Outputs
		-------
		filein.outfields
		"""
	
		#Defaults
		if 'infields' not in inputs or inputs['infields'] is None:
			infields=['sub_id','scan_id','uid']
		else:
			infields=inputs['infields']
		if 'exts' not in inputs or inputs['exts'] is None:
			exts = {'nifti':'.nii.gz'}
		else:
			exts = inputs['exts']
		if 'outfields' not in inputs or inputs['outfields'] is None:
			outfields=['nifti']
		else:
			outfields=inputs['outfields']
		if 'template' not in inputs or inputs['template'] is None:
			template='%s/%s/%s_%s_%s.ext'
		else:
			template=inputs['template']
		if 'sort_filelist' not in inputs or inputs['sort_filelist'] is None:
			sort_filelist = True
		else:
			sort_filelist = inputs['sort_filelist']
		if 'base_directory' not in inputs or inputs['base_directory'] is None:
			base_directory = os.getcwd()
		else:
			base_directory = inputs['base_directory']
			
		lof = len(outfields)
		lex = len(exts)
		if 'field_template' not in inputs or \
		inputs['field_template'] is None or \
		len(inputs['field_template']) != lof:
			if lof != lex:
				raise ValueError('len(outfields): %d != len(ext) %d' % (lof, lex))
			field_template = dict()
			for i in range(0,lof):
				field_template.update(
					{outfields[i]:template.replace('.ext',exts[outfields[i]])})
		else:
			field_template = inputs['field_template']
			outfields = field_template.keys()
			
		if 'templat_args' not in inputs or inputs['template_args'] is None:
			template_args = dict()
			for i in range(0,lof):
				template_args.update(
					{outfields[i]:
						[['sub_id','scan_id','sub_id','scan_id','uid']]})
		else:
			template_args = inputs['template_args']
					
		#Create DataGrabber node
		super(FileIn, self).__init__(name=name, 
			interface=nio.DataGrabber(infields=infields, outfields=outfields), 
			**kwargs)
		#datain = pe.Node(
			#name='filein',
			#interface=nio.DataGrabber(infields=infields,outfields=outfields))
			
		self.inputs.base_directory = base_directory
		self.inputs.template = template
		self.inputs.field_template = field_template
		self.inputs.template_args = template_args
		self.inputs.sort_filelist = sort_filelist
	
		#self.add_nodes([datain])

class FileOut(DINGOflow):
	_inputnode = 'inputnode'
	_outputnode = 'sink'
	
	connection_spec = {
		'sub_id'			:	['SplitIDs','sub_id'],
		'scan_id'			:	['SplitIDs','scan_id'],
		'uid'				:	['SplitIDs','uid']
	}
	
	def __init__(self, name='FileOut_SubScanUID',\
	inputs={'pnames':None, 'substitutions':None, 'in_files':None,\
	'parent_dir':None, 'sub_id':None, 'scan_id':None, 'uid':None},\
	**kwargs):
		"""
		Parameters
		----------
		name 				:	Workflow name
		pnames				:	List of parent flow names determine subcontainer
		in_files			:	List of files to write
		substitutions		:	List of tuple pairs for filename substitutions
			('input_id' substitute will be replaced with subid_scanid_uid)
			e.g. [('input_id','id'),('dtifit_','input_id')] ->
				['input_id','id'),('dtifit_','subid_scanid_uid')]
			
		Returns
		-------
		fileout Nipype workflow
		
		Inputs
		------
		inputnode.parent_dir		:	directory of subject folders
		inputnode.sub_id			:	subject id
		inputnode.scan_id			:	scan id
		inputnode.uid				:	unique id
		inputnode.in_files			:	files to write
		
		Outputs
		-------
		Files written to parent_dir/sub_id/scan_id/pnames
		"""

		super(FileOut, self).__init__(name=name, **kwargs)
		
		inputnode = pe.Node(name='inputnode',
			interface=IdentityInterface(
				fields=['parent_dir','sub_id','scan_id','uid','in_files'], 
				mandatory_inputs=True))
				
		if 'parent_dir' in inputs and inputs['parent_dir'] is not None:
			inputnode.inputs.parent_dir = parent_dir
		if 'sub_id' in inputs and inputs['sub_id'] is not None:
			inputnode.inputs.sub_id = sub_id
		if 'scan_id' in inputs and inputs['scan_id'] is not None:
			inputnode.inputs.scan_id = scan_id
		if 'uid' in inputs and inputs['uid'] is not None:
			inputnode.inputs.uid = uid
		if 'in_files' in inputs and inputs['in_files'] is not None:
			inputnode.inputs.in_files = in_files
		
		util = pe.Node(
			name='util',
			interface=Function(
				input_names=['names','file_list','substitutions',
					'sub_id','scan_id','uid'],
				output_names=['container','out_file_list','newsubs'],
				function=fileout_util))
		util.inputs.names = pnames
		if 'substitutions' not in inputs or inputs['substitutions'] is None:
			substitutions = []
		util.inputs.substitutions = substitutions	
		
		sink = pe.Node(name='sink', interface=nio.DataSink())
		sink.inputs.parameterization = False
		
		self.connect([
			(inputnode, util,
				[('sub_id','sub_id'),
				('scan_id','scan_id'),
				('uid','uid'),
				('in_files','file_list')]),
			(inputnode, sink, 
				[('parent_dir','base_directory')]),
			(util, sink,
				[('container','container'),
				('out_file_list','outfields'),
				('newsubs','substitutions')])
			])
		
	
def run_fileout(name='fileout',\
inputs={'pnames':None, 'substitutions':None, 'in_files':None,\
'parent_dir':None, 'sub_id':None, 'scan_id':None, 'uid':None}):
	"""create_fileout then run it - Sink files"""
	fo = FileOut(name=name, pnames=pnames, substitutions=substitutions,
		in_files=in_files, parent_dir=parent_dir, 
		sub_id=sub_id, scan_id=scan_id, uid=uid)
	fo.run()
	return fo.result.outputs
	
	
#see if MapNode of Function will work instead
def wrapJoin(name='wrapJoin',
module='nipype.interfaces.utility',interface='IdentityInterface',fields=None):
	m, f = DynImport(mod=module, obj=interface)
	#TODO finish implementation
	
	return None

#fajoin = pe.JoinNode(
			#name='fajoin',
			#interface=IdentityInterface(
				#fields=['fa_']),
			#joinsource='inputnode',
			#joinfield=['fa_'])
			
		#containerjoin = pe.JoinNode(
			#name='containerjoin',
			#interface=IdentityInterface(
				#fields=['container_']),
			#joinsource='inputnode',
			#joinfield=['container_'])
