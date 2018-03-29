import os
from nipype import config, logging
from DINGO.utils import (read_config, split_chpid, join_strs)
from DINGO.base import DINGO, DINGOflow, DINGOnode
from nipype import IdentityInterface, SelectFiles, Function
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio

#config.enable_debug_mode()
#logging.update_logging(config)
	
class HelperFlow(DINGO):
	
	def __init__(self, workflow_to_module=None, **kwargs):
		wfm = {
		'SplitIDs'				:	'DINGO.wf',
		'SplitIDs_iterate'		:	'DINGO.wf',
		'FileIn'				:	'DINGO.wf',
		'FileIn_SConfig'		:	'DINGO.wf',
		'FileOut'				:	'DINGO.wf',
		'DICE'					:	'DINGO.wf'
		}
		
		if workflow_to_module is None:
			workflow_to_module = wfm
		else:
			for k,v in wfm.iteritems():
				if k not in workflow_to_module:
					workflow_to_module.update({k:v})
		
		super(HelperFlow, self).__init__(
			workflow_to_module=workflow_to_module,
			**kwargs
		)
		
class DICE(DINGOflow):
	"""Nipype node to output dice image and coefficient for lists of niftis
	
	Inputs
	------
	inputnode.nii_list_A
	inputnode.nii_list_B
	inputnode.tract_names - so that nifti lists don't have to be guaranteed to 
		match this parameter is used to search the filename and pass match on
	inputnode.base_dir
	inputnode.sub_id
	inputnode.scan_id
	inputnode.uid
	inputnode.sep - separator for output file basename, default '_'
	
	Outputs
	-------
	dicenode.img
	dicenode.coef
	"""
	_inputnode = 'inputnode'
	_outputnode = 'dicenode'
	connection_spec = {
		'sub_id'			:	['SplitIDs','sub_id'],
		'scan_id'			:	['SplitIDs','scan_id'],
		'uid'				:	['SplitIDs','uid']
	}
	
	def __init__(self, name='DICE', inputs={}, **kwargs):
		super(DICE, self).__init__(name=name, **kwargs)
		
		input_fields = ['nii_list_A','nii_list_B', 'tract_names',
						'base_dir','sub_id','scan_id','uid','sep','subfolder']
		input_iters = ('tract_names', inputs['tract_names'])
		
		inputnode = pe.Node(
			name='inputnode',
			interface=IdentityInterface(fields=input_fields),
			iterables=input_iters)
			
		for elt in input_fields:
			if elt in inputs and inputs[elt] is not None:
				setattr(inputnode.inputs, elt, inputs[elt])
		
		getA = pe.Node(
			name='getA',
			interface=Function(
				input_names=['tract_list','tract_name'],
				output_names=['tract'],
				function=DICE.get_tract))
					
		getB = pe.Node(
			name='getB',
			interface=Function(
				input_names=['tract_list','tract_name'],
				output_names=['tract'],
				function=DICE.get_tract))
		
		dicenode = pe.Node(
			name='dicenode',
			interface=Function(
				input_names=['nii_A','nii_B', 'output_bn'],
				output_names=['img','coef'],
				function=DICE.dice_coef))
		
		create_bn = pe.Node(
			name='create_bn',
			interface=Function(
				input_names=['sep','subfolder','nii',
				'basedir','subid','scanid','uid'],
				output_names=['file'],
				function=DICE.create_basename))
				
		#Connect
		self.connect([
			(inputnode, getA, [
				('nii_list_A', 'tract_list'),
				('tract_names', 'tract_name')]),
			(inputnode, getB, [
				('nii_list_B', 'tract_list'),
				('tract_names', 'tract_name')]),
			(inputnode, create_bn, [
				('sep', 'sep'),
				('subfolder', 'subfolder'),
				('base_dir', 'basedir'),
				('sub_id', 'subid'),
				('scan_id', 'scanid'),
				('uid', 'uid')]),
			(getA, dicenode, [
				('tract', 'nii_A')]),
			(getB, dicenode, [
				('tract', 'nii_B')]),
			(getB, create_bn, [
				('tract', 'nii')]),
			(create_bn, dicenode, [
				('file', 'output_bn')])
		])
		
	def get_tract(tract_list, tract_name):
		"""Takes a list of tract file strings and single tract name, returns the 
		matching tract from list
		
		tract_list = ['path/to/..._tract_name0.trk...',
					  '/path/to/tract_name1.trk...']
		tract_name = 'tract_name1'
		tract = get_tract(tract_list, tract_name)
		tract -> '/path/to/tract_name1.trk...'
		
		Will raise if tract not matched, or more than one match.
		"""
		import re
		pattern = ''.join(('(?<=[\\\\_\/])(?P<tract>',tract_name,')(?=\.trk)'))
		comp = re.compile(pattern)
		searchall = [re.search(comp, t) for t in tract_list]
		tractsearch = filter(lambda x: x is not None, searchall)
		if len(tractsearch) == 1:
			index = searchall.index(tractsearch[0])
			tract = tract_list[index]
		elif not tractsearch:
			raise LookupError('Did not find tract: %s' % tract_name)
		else:
			raise LookupError('Found more than one matching tract: %s' 
			% tract_name)
		return tract
	
	def create_basename(nii=None, 
	basedir=None, subid=None, scanid=None, uid=None, subfolder='', sep='_'):
		"""Takes a file along with basedir, subid, scanid, uid, subfolder 
		strings and returns a new filename.
		
		Parameters
		------
		nii			:	Str
		basedir		:	Str
		subid		:	Str - subfolder to basedir and leads new filename
		scanid		:	Str - subfolder to subid, after subid in filename
		uid			:	Str - after scanid in filename
		subfolder	:	Str - subfolder to scanid, default nothing
		sep			:	Str - default '_'
		
		Returns
		-------
		basename	:	Str
			basename = '_'.join((subid, scanid, uid, tract, 'DICE'))
			os.path.join(basedir, subid, scanid, subfolder, basename)
		"""
		import os
		import re
		from nipype.interfaces.base import isdefined
		
		if not isdefined(subfolder):
			path = os.path.join(basedir, subid, scanid)
		else:
			path = os.path.join(basedir, subid, scanid, subfolder)
		try:
			os.mkdir(path)
		except OSError:
			pass
		
		if not isdefined(sep):
			sep = '_'
		if nii and basedir and subid and scanid and uid:
			pattern = '(?<=[\\\\_\/])(?P<tract>\w*)(?=\.trk)'
			thissearch = re.search(pattern, nii)
			if thissearch:
				tract = thissearch.group('tract')
				basename = sep.join((subid, scanid, uid, 'DICE', tract))
			else:
				print('Could not find tract name in nii: %s' % nii)
				basename = sep.join((subid, scanid, uid, 'DICE'))
				
			return os.path.join(path, basename)
				
	def dice_coef(nii_A, nii_B, output_bn):
		"""
		Dice Coefficient:
			D = 2*(A == B)/(A)+(B)

		Input is two binary masks in the same 3D space
		NII format

		Output is a DICE score and overlap image
		"""
		
		from nipy import load_image, save_image
		import numpy as np
		import getpass
		from nipy.core.api import Image, vox2mni
		
		imageA = load_image(nii_A)
		dataA = imageA.get_data()
		sumA = np.sum(dataA)
		coord = imageA.coordmap


		imageB = load_image(nii_B)
		dataB = imageB.get_data()
		sumB = np.sum(dataB)

		overlap = dataA + dataB
		intersect = overlap[np.where(overlap==2)].sum()

		dice = intersect/(sumA + sumB)

		def save_nii(data,coord, save_file):
			arr_img = Image(data, coord)
			img = save_image(arr_img, save_file)
			return img
			
		def save_txt(dice, save_file_bn):
			save_file = ''.join((save_file_bn,'.txt'))
			f = open(save_file, 'w')
			f.write('{0}'.format(dice))
			f.close()
			return save_file

		img = save_nii(overlap, coord, output_bn)
		coef = save_txt(dice, output_bn)
		return img, coef
	
class SplitIDs(DINGOnode):
	"""Nipype node to split a CHP_ID into separate subject, scan and task ids
	
	Parameters
	----------
	name				:	Str (workflow name, default 'SplitIDs')
	inputs				:	Dict
		parent_dir		:	Directory (base directory)
		id				:	Str
		id_sep			:	Str (default '_')
	kwargs				:	Nipype Node Kwargs
	
	Node Inputs
	-----------
	psid				:	Str
	sep					:	Str
	
	Node Outputs
	------------
	sub_id				:	Str
	scan_id				:	Str
	uid					:	Str
	"""
	
	connection_spec = {
		'psid'		:	['Config','included_ids']
	}
	
	def __init__(self, name='SplitIDs',\
	inputs={'parent_dir':None,'id':None,'id_sep':'_'}, **kwargs):
		
		if 'parent_dir' in inputs and inputs['parent_dir'] is not None:
			self.base_dir = inputs['parent_dir']
			
		super(SplitIDs, self).__init__(
			name=name,
			interface=Function(
				input_names=['psid','sep'],
				output_names=['sub_id','scan_id','uid'],
				function=split_chpid),
			**kwargs)
			
		if 'id' in inputs and inputs['id'] is not None:
			self.inputs.psid = inputs['id']
		if 'id_sep' in inputs and inputs['id_sep'] is not None:
			self.inputs.sep = inputs['id_sep']
			
			
class SplitIDs_iterate(DINGOflow):
	"""Nipype node to iterate a list of ids into separate subject, scan, and
	task ids.
	
	Parameters
	----------
	name				:	Str (workflow name, default 'SplitIDs')
	inputs				:	Dict
		parent_dir		:	Directory (base directory)
		scan_list		:	List[Str] 
		scan_list_sep	:	Str (separator for fields in id)
	kwargs				:	Nipype Workflow Kwargs
		
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
	_inputnode = 'inputnode'
	_outputnode = 'outputnode'
	
	def __init__(self, name='SplitIDs',\
	inputs={'parent_dir':None,'scan_list':None,'scan_list_sep':'_'}, **kwargs):
		
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
	connection_spec = {
		'sub_id'			:	['SplitIDs','sub_id'],
		'scan_id'			:	['SplitIDs','scan_id'],
		'uid'				:	['SplitIDs','uid']
	}
	
	def __init__(self, name='FileIn_SubScanUID',\
	inputs={'infields':None, 'outfields':None, 'exts':None, 'template':None,\
	'field_template':None, 'template_args':None, 'sort_filelist':True},\
	**kwargs):
	
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
			
		if 'template_args' not in inputs or inputs['template_args'] is None:
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
			
		self.inputs.base_directory = base_directory
		self.inputs.template = '*'
		self.inputs.field_template = field_template
		self.inputs.template_args = template_args
		self.inputs.sort_filelist = sort_filelist
	
	
class FileIn_SConfig(DINGOflow):
	"""Nipype workflow to get files specified in a subject config.json
	
	Mandatory Inputs - either in dict arg inputs or connected to inputnode
	----------------
	base_directory		:	Str
	outfields			:	List[Str]
	sub_id				:	Str
	scan_id				:	Str
	uid					:	Str
	
	Optional Inputs - in dict arg inputs or connected to create_ft
	---------------
	repl				:	List or Dict
	"""
	_inputnode = 'inputnode'
	_outputnode = 'filein'
	
	connection_spec = {
		'sub_id'			:	['SplitIDs','sub_id'],
		'scan_id'			:	['SplitIDs','scan_id'],
		'uid'				:	['SplitIDs','uid']
	}
	
	def __init__(self, name='FileIn_SConfig',\
	inputs=None,\
	**kwargs):
		if inputs is None:
			inputs = {}
		super(FileIn_SConfig, self).__init__(name=name, **kwargs)
		
		inputnode = pe.Node(
			name='inputnode',
			interface=IdentityInterface(
				fields=[
					'base_directory',
					'outfields',
					'sub_id',
					'scan_id',
					'uid']),
			mandatory_inputs=True)
			
		if 'base_directory' in inputs and inputs['base_directory'] is not None:
			inputnode.inputs.base_directory = inputs['base_directory']
		if 'outfields' in inputs and inputs['outfields'] is not None:
			inputnode.inputs.outfields = inputs['outfields']
		else:
			raise KeyError('inputs["outfields"] must be specified to instantiate %s' 
				% self.__class__)
		if 'sub_id' in inputs and inputs['sub_id'] is not None:
			inputnode.inputs.sub_id = inputs['sub_id']
		if 'scan_id' in inputs and inputs['scan_id'] is not None:
			inputnode.inputs.scan_id = inputs['scan_id']
		if 'uid' in inputs and inputs['uid'] is not None:
			inputnode.inputs.uid = inputs['uid']
			
		cfgpath = pe.Node(
			name='cfgpath',
			interface=Function(
				input_names=[
					'base_directory',
					'sub_id',
					'scan_id',
					'uid'],
				output_names=['path'],
				function=self.cfgpath_from_ids))
				
		read_conf = pe.Node(
			name='read_conf',
			interface=Function(
				input_names=['configpath'],
				output_names=['configdict'],
				function=read_config))
				
		create_ft = pe.Node(
			name='create_field_template',
			interface=Function(
				input_names=[
					'base_directory',
					'sub_id',
					'scan_id',
					'uid',
					'config',
					'path_keys',
					'repl'],
				output_names=['field_template'],
				function=self.create_field_template))
				
		if 'repl' in inputs and inputs['repl'] is not None:
			create_ft.inputs.repl = inputs['repl']
				
		filein = pe.Node(
				name='filein',
				interface=nio.DataGrabber(outfields=inputs['outfields']))
		filein.inputs.template = '*'
		filein.inputs.sort_filelist = True
				
		self.connect([
			(inputnode, cfgpath, [('base_directory','base_directory'),
								('sub_id','sub_id'),
								('scan_id','scan_id'),
								('uid','uid')]),
			(inputnode, create_ft, [('base_directory','base_directory'),
									('sub_id','sub_id'),
									('scan_id','scan_id'),
									('uid','uid'),
									('outfields','path_keys')]),
			(inputnode, filein, [('base_directory','base_directory')]),
			(cfgpath, read_conf, [('path','configpath')]),
			(read_conf, create_ft, [('configdict','config')]),
			(create_ft, filein, [('field_template','field_template')])
			])

	def cfgpath_from_ids(base_directory=None, sub_id=None, scan_id=None, uid=None):
		if base_directory is not None and \
		sub_id is not None and \
		scan_id is not None and \
		uid is not None:
			import os
			cfgname = []
			cfgname.extend((sub_id,scan_id,uid,'config.json'))
			cfgname = '_'.join(cfgname)
			return os.path.join(base_directory, sub_id, scan_id, cfgname)
			
	def create_field_template(base_directory=None, sub_id=None, scan_id=None, uid=None,\
		config=None, path_keys=None, repl=None):
			import os
			defrepl = {
				'pid'			:	sub_id,
				'scanid'		:	scan_id,
				'sequenceid'	:	uid,
				'parent_dir'	:	base_directory
			}
			#set up replacement dict
			if repl is None:
				myrepl = defrepl
			else:
				myrepl = dict()
				if isinstance(repl, (list,tuple)):
					for e in repl:
						myrepl.update({e:'placeholder'})
				elif isinstance(repl, (str,unicode)):
					myrepl.update({repl:'placeholder'})
				elif isinstance(repl, dict):
					myrepl = repl
				for k,v in defrepl.iteritems():
					if k not in myrepl:
						myrepl.update({k:v})
			#get or compare (error check) to config
			values = [None] * len(myrepl)
			for k,v in myrepl.iteritems():
				if v == 'placeholder':
					myrepl.update({k:config['paths'][k]})
				elif config[k] != v:
					raise Exception('Subject config error[%s]: '
						'Expecting %s, Got %s'
						% (k, v, config[k]))			
			#create field template dict
			field_template = {}
			for pathkey in path_keys:
				value = config['paths'][pathkey]
				dirkey = '_'.join((pathkey, 'dir'))
				if dirkey in config['paths']:
					dirvalue = config['paths'][dirkey]
				else:
					dirvalue = ''
				value = os.path.join(dirvalue, config['paths'][pathkey])
				for k,v in myrepl.iteritems():
					value = value.replace(k, v)
				field_template.update({pathkey:value})
				
			return field_template
		

class FileOut(DINGOflow):
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
	_inputnode = 'inputnode'
	_outputnode = 'sink'
	
	connection_spec = {
		'sub_id'			:	['SplitIDs','sub_id'],
		'scan_id'			:	['SplitIDs','scan_id'],
		'uid'				:	['SplitIDs','uid']
	}
	
	def __init__(self, name='FileOut_SubScanUID',\
	inputs=dict(substitutions=None, s2r='input_id', infields=None,\
	parent_dir=None, sub_id=None, scan_id=None, uid=None),\
	**kwargs):

		super(FileOut, self).__init__(name=name, **kwargs)
		
		inputfields = ['parent_dir','sub_id','scan_id','uid']
		if 'infields' in inputs and inputs['infields'] is not None:
			infields = inputs['infields']
		else:
			infields = []
		inputfields.extend((field.replace('.','_') for field in infields ))
		inputnode = pe.Node(name='inputnode',
			interface=IdentityInterface(
				fields=inputfields), 
			mandatory_inputs=True)
		
		if 'parent_dir' in inputs and inputs['parent_dir'] is not None:
			inputnode.inputs.parent_dir = inputs['parent_dir']
		if 'sub_id' in inputs and inputs['sub_id'] is not None:
			inputnode.inputs.sub_id = inputs['sub_id']
		if 'scan_id' in inputs and inputs['scan_id'] is not None:
			inputnode.inputs.scan_id = inputs['scan_id']
		if 'uid' in inputs and inputs['uid'] is not None:
			inputnode.inputs.uid = inputs['uid']
		
		cont = pe.Node(
			name='container',
			interface=Function(
				input_names=['sub_id', 'scan_id'],
				output_names=['cont_string'],
				function=self.container))
				
		prefix = pe.Node(
			name='prefix',
			interface=Function(
				input_names=['sep','arg0','arg1','arg2'],
				output_names=['pref_string'],
				function=join_strs))
		prefix.inputs.sep = '_'
		
		subs = pe.Node(
			name='substitutions',
			interface=Function(
				input_names=['subs','s2r','rep'],
				output_names=['new_subs'],
				function=self.substitutions))
		if 'substitutions' in inputs and inputs['substitutions'] is not None:
			subs.inputs.subs = inputs['substitutions']
		if 's2r' in inputs and inputs['s2r'] is not None:
			subs.inputs.s2r = inputs['s2r']
		
		sink = pe.Node(name='sink', interface=nio.DataSink(infields=infields))
		sink.inputs.parameterization = False
		
		for field in infields:
			self.connect([
				(inputnode, sink, 
					[(field.replace('.','_'), field )])
				])
		
		self.connect([
			(inputnode, cont,
				[('sub_id','sub_id'),
				('scan_id','scan_id')]),
			(inputnode, prefix, 
				[('sub_id','arg0'),
				('scan_id','arg1'),
				('uid','arg2')]),
			(inputnode, sink,
				[('parent_dir','base_directory')]),
			(prefix, subs,
				[('pref_string','rep')]),
			(cont, sink,
				[('cont_string','container')]),
			(subs, sink,
				[('new_subs','substitutions')])
			])
					
	def container(sub_id=None, scan_id=None):
		import os.path as op
		return op.join(sub_id, scan_id)
		
	def substitutions(subs=None, s2r=None, rep=None):
		from traits.trait_base import _Undefined
		if s2r is None or rep is None:
			if subs is None:
				return _Undefined()
			else:
				return subs
		else:
			newsubs = []
			for pair in subs:
				newpair = (pair[0], pair[1].replace(s2r, rep))
				newsubs.append(newpair)
		return newsubs
	
