import os
from DINGO.utils import DynImport, read_config, tobool, reverse_lookup
import nipype.pipeline.engine as pe
from nipype import IdentityInterface


class DINGO(pe.Workflow):
	"""Create a workflow from a json config file"""
	
	workflow_to_module = {
		'SplitIDs'					:	'DINGO.wf',
		'IterateIDs'				:	'DINGO.wf',
		'FileIn'					:	'DINGO.wf',
		'FileIn_SConfig'			:	'DINGO.wf',
		'FileOut'					:	'DINGO.wf',
		'Reorient'					:	'DINGO.fsl',
		'EddyC'						:	'DINGO.fsl',
		'BET'						:	'DINGO.fsl',
		'DTIFIT'					:	'DINGO.fsl',
		'FLIRT'						:	'DINGO.fsl',
		'FNIRT'						:	'DINGO.fsl',
		'ApplyWarp'					:	'DINGO.fsl',
		'FSL_nonlinreg'				:	'DINGO.fsl',
		'TBSS_prereg'				:	'DINGO.fsl',
		'TBSS_reg_NXN'				:	'DINGO.fsl',
		'TBSS_postreg'				:	'DINGO.fsl',
		'DSI_SRC'					:	'DINGO.DSI_Studio',
		'REC_prep'					:	'DINGO.DSI_Studio',
		'DSI_REC'					:	'DINGO.DSI_Studio',
		'DSI_TRK'					:	'DINGO.DSI_Studio',
		'create_reorient'			:	'DINGO.fsl',
		'create_eddyc'				:	'DINGO.fsl',
		'create_bet'				:	'DINGO.fsl',
		'create_dtifit'				:	'DINGO.fsl',
		'create_genFA'				:	'DINGO.fsl',
		'create_flirt'				:	'DINGO.fsl',
		'create_fnirt'				:	'DINGO.fsl',
		'create_ind_nonlinreg'		:	'DINGO.fsl',
		'create_nonlinreg'			:	'DINGO.fsl',
		'create_invwarp_all2best'	:	'DINGO.fsl',
		'create_warp_regions'		:	'DINGO.fsl',
		'create_applywarp'			:	'DINGO.fsl',
		'create_tbss_registration'	:	'DINGO.fsl'
	}

	subflows = dict()#could be workflows as well
	workflow_connections = dict()
	workflow_params = dict()
	
	def __init__(self, workflow_to_module=None, configpath=None, name=None,\
	**kwargs):
		if name is None:
			name = 'DINGO'
		super(DINGO,self).__init__(name=name,**kwargs)
		
		if workflow_to_module is not None:
			self.update_wf_to_mod_map(**workflow_to_module)
		
		if configpath is None:
			self.configpath = None
			print('run %s.create_wf_from_config(configpath) to add subworkflows'
				% self)
		else:
			self.configpath = configpath
			self.create_wf_from_config(configpath)
			
	def update_wf_to_mod_map(self, **updates):
		self.workflow_to_module.update(**updates)
	
	@classmethod
	def wf_to_mod(cls, wf):
		"""Get module containing func for creation given nipype workflow name
		
		Parameters
		----------
		wf		:	String specifiying the workflow
		
		Returns
		-------
		module	:	Module str containing function that will create the workflow
		"""
		try:
			return cls.workflow_to_module[wf]
		except KeyError:
			msg = 'Workflow: %s not associated with a module' % wf
			raise KeyError(msg)
	
							
	def check_input_field(self, cfg_bn, cfg, keyname, exptype):
		if keyname not in cfg:
			raise KeyError('Analysis config: %s, missing required key ["%s"]' %
				(cfg_bn, keyname))
		elif not isinstance(cfg[keyname], exptype):
			raise TypeError('Analysis config: %s, ["%s"] is not a %s'
				'Type: %s, Value: %s' %
				(cfg_bn, keyname, exptype, 
				type(cfg[keyname]), cfg[keyname]))
					
							
	def check_input_fields(self, cfg_bn, cfg, expected_keys):
		"""Loop through expected_keys
		Check if each 0th element has 1st element type
		"""
		input_fields = {}
		alternatives = {}
		
		for keytuple in expected_keys:
			if isinstance(keytuple[0], (unicode,str)):
				keyname = keytuple[0]
				valtype = keytuple[1]
			elif isinstance(keytuple[0], (tuple,list)):
				#alternatives to check are subsequent elements
				#sublevel implies mutually inclusive alternatives
				keyname = keytuple[0][0]
				valtype = keytuple[0][1]
				alternatives.update({keytuple[0][0]:keytuple[1:]})
			try:
				self.check_input_field(cfg_bn, cfg, keyname, valtype)
				input_fields.update({keyname:cfg[keyname]})
			except:
				if keyname in alternatives.keys():
					alt = alternatives[keyname]
					if isinstance(alt[0], (unicode,str)):
						keyname = alt[0]
						valtype = alt[1]
						self.check_input_field(cfg_bn, cfg, keyname, valtype)
						input_fields.update({keyname:cfg[keyname]})
					elif isinstance(alt[0], (tuple,list)):
						for altpair in alt:
							keyname = altpair[0]
							valtype = altpair[1]
							self.check_input_field(cfg_bn, cfg, keyname,valtype)
							input_fields.update({keyname:cfg[keyname]})
				else:
					raise
		return input_fields
		
		
	def create_subwf(self, step, name):
		"""update subwf.inputs with self.input_params[subwfname]
		add subwf to self.subflows[subwfname]
		"""
		_, obj = DynImport(mod=self.wf_to_mod(step), obj=step)
		ci = self.get_node('config_inputs')
		for paramkey, paramval in self.input_params[name].iteritems():
			if isinstance(paramval, (str,unicode)) and \
			hasattr(ci.inputs, paramval):
				cival = getattr(ci.inputs, paramval)
				self.input_params[name].update({paramkey:cival})
		self.subflows[name] = obj(name=name, inputs=self.input_params[name])
	
	def make_connection(self, srcobj, srcfield, destobj, destfield):
		"""Connect srcfield and destfield, allow for nodes and workflows"""
		if issubclass(type(srcobj), pe.Node):
			srcname = (srcfield,)
		elif issubclass(type(srcobj), pe.Workflow):
			if hasattr(srcobj, '_outputnode'):
				srcname = (srcobj._outputnode, srcfield)
			else:
				srcname = ('outputnode', srcfield)
		srcname = '.'.join(srcname)
		
		if issubclass(type(destobj), pe.Node):
			destname = (destfield,)
		elif issubclass(type(destobj), pe.Workflow):
			if hasattr(destobj, '_inputnode'):
				destname = (destobj._inputnode, destfield)
			else:
				destname = ('inputnode', destfield)
		destname = '.'.join(destname)
					
		self.connect(srcobj, srcname, destobj, destname)
		print('Connected %s.%s --> %s.%s' % 
			(srcobj.name, srcname, destobj.name, destname))
		
	def connect_subwfs(self):
		"""update subwf.connection_spec with self.input_connections[subwfname]
		and connect subwfs
		"""
		for destkey, destobj in self.subflows.iteritems():
			#name, obj
			try:
				destobj.connection_spec.update(
					self.input_connections[destkey])
			except AttributeError:
				#simple attempt to support non DINGO
				destobj.connection_spec = {}
				destobj.connection_spec.update(
					self.input_connections[destkey])
				
			self.workflow_connections[destkey] = destobj.connection_spec
			
			for destfield, values in \
			self.workflow_connections[destkey].iteritems():
				testsrckey = values[0]
				srcfield = values[1]
				
				if testsrckey in self.name2step:
					#connection from config, or at least name==step
					srckey = testsrckey
				elif self.name2step.values().count(testsrckey) > 1:
					raise Exception('Step: %s used more than once, default'
						'connections will not work. Add ["method"]["Name"]'
						'["connect"] for linked downstream nodes.')
				else:
					#testsrckey is step that appears once, name!=step
					try:
						srckey = reverse_lookup(self.name2step, testsrckey)
					except ValueError:
						print('destkey: %s' % destkey)
						raise
					
				srcobj = self.subflows[srckey]
				self.make_connection(srcobj, srcfield, destobj, destfield)
		
			
	def create_wf_from_config(self, cfgpath, expected_keys=None):
		"""Create and connect steps provided in json configuration file.
		
		Parameters
		----------
		cfgpath		:	filepath to json configuration
		
		Updates
		-------
		Nipype Workflow
		Node config_inputs[expected_keys]
			name				:	Str
			data_dir			:	Path
			included_ids		:	List[Str]
				included_ids['SubjectId_ScanId_UniqueID']
		input_params		:	Dict[Dict]
			input_params{subflowname{paramname:paramvalue}}
		input_connections	:	Dict[Dict[List[List]]]
			input_connections{subflowname{precedingflowname[[output,input]]}}
		subflows			:	Dict[Workflow/Node]
			subflows{subflow}
		"""
		
		#cfgpath = '/home/pirc/Desktop/DWI/DINGO/res/Neonates_analysis_config.json'
		
		#Read config file
		if cfgpath is None:
			raise NameError('Required cfgpath unspecified')
		cfg = read_config(cfgpath)
		cfg_bn = os.path.basename(cfgpath)
		
		#Check important config keys
		if expected_keys is None:
			expected_keys = (
				('name', (unicode,str)),
				('data_dir', (unicode,str)),
				('steps', list),
				('method', dict),
				(('included_ids', list), (
					('included_imgs', list), ('included_masks', list)))
			)
		#expected keynames should be toplevel fields in the config
		input_fields = self.check_input_fields(cfg_bn, cfg, expected_keys)
		if 'data_dir' in input_fields:
			self.base_dir = input_fields['data_dir']
		if 'name' in input_fields:
			self.name = input_fields['name']

		#Set up from config
		config_inputs = pe.Node(name='config_inputs', 
			interface=IdentityInterface(
				fields=input_fields.keys()))
			
		iterablelist = []	
		for field, value in input_fields.iteritems():
			setattr(config_inputs.inputs, field, value)
			if isinstance(value, list) and value != 'steps':
				iterablelist.append((field, value))
		if len(iterablelist) > 0:
			setattr(config_inputs, 'iterables', iterablelist)
		
		previousci = self.get_node('config_inputs')
		if previousci is not None:
			self.remove_nodes([previousci])
		self.add_nodes([config_inputs])
		
		self.subflows = dict()
		self.input_params = dict()
		self.input_connections = dict()
		self.name2step = dict()
		
		method = input_fields['method']
		
		for nameandstep in input_fields['steps']:
			if isinstance(nameandstep, list):
				if len(nameandstep) == 1:
					step = nameandstep[0]
					name = nameandstep[0]
				elif len(nameandstep) == 2:
					step = nameandstep[1]
					name = nameandstep[0]
			elif isinstance(nameandstep, (unicode, str)):
				step = nameandstep
				name = nameandstep
			self.name2step.update({name:step})
			#Get changes to defaults from config file
			if not isinstance(step, (str,unicode)) or \
			not isinstance(name, (str,unicode)):
				raise TypeError('Analysis Config: %s, Invalid configuration.\n'
					'Step: %s, of type "%s" and Name: %s, of type "%s" '
					'must be str or unicode' %
					(cfg_bn, step, type(step), name, type(name)))
			else:
				if name in self.subflows:
					raise KeyError('Analysis Config: %s, Invalid configuration.'
						'\nDuplicates of Name: %s' % 
						(cfg_bn, name))
				if name in method and 'inputs' in method[name]:
					#inputs are flags for the function creating the workflow
					#used in various fashions
					inputs  = method[name]['inputs']
					if not isinstance(inputs, dict):
						raise TypeError('Analysis Config: %s, '
							'["method"]["%s"]["inputs"] is not a dict. '
							'Value: %s, Type: %s' %
							(cfg_bn, name, inputs, type(inputs)))
					self.input_params[name] = inputs
				else:
					self.input_params[name] = {}
				if name in method and 'connect' in method[name]:
					#connect are changes to the defaults in connection spec
					connections = method[name]['connect']
					if not isinstance(connections, dict):
						raise TypeError('Analysis Config: %s, '
							'["method"]["%s"]["connect"] is not a dict. '
							'Value: %s, Type: %s' %
							(cfg_bn, name, connections, type(connections)))
					for destfield, values in connections.iteritems():
						if not isinstance(destfield, (str,unicode)) or \
						not isinstance(values, (list,tuple)) or \
						not isinstance(values[0], (str,unicode)) or \
						not isinstance(values[1], (str,unicode)):
							raise TypeError('Analysis Config: %s, '
								'["method"]["%s"]["connect"] does not contain'
								' appropriate types. Key: %s, Value: %s' %
								(cfg_bn, name, destfield, values))
					self.input_connections[name] = connections
				else:
					self.input_connections[name] = {}
			print('Create Workflow/Node Name:%s, Obj:%s' % (name, step))
			self.create_subwf(step, name)
			
		self.connect_subwfs()
	

class DINGOflow(pe.Workflow):
	"""Add requisite properties to Nipype Workflow. Output folder 'Name', will 
	be in top level of nipype cache with its own parameterized iterables 
	folders.
	"""
	_inputnode = None
	_outputnode = None
	_joinsource = 'config_inputs'
	connection_spec = {}
	
	def __init__(self, connection_spec=None, **kwargs):
		super(DINGOflow,self).__init__(**kwargs)
		
		if connection_spec is not None:
			self.connection_spec.update(connection_spec)
			
			
class DINGOnode(pe.Node):
	"""Add requisite properties to Nipype Node. Output folder 'Name', will be in
	 the parameterized iterables folders.
	 """
	_joinsource = 'config_inputs'
	connection_spec = {}
	
	def __init__(self, connection_spec=None, **kwargs):
		super(DINGOnode,self).__init__(**kwargs)
		
		if connection_spec is not None:
			self.connection_spec.update(connection_spec)
	
