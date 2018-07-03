from nipype import config, logging
import os
from DINGO.utils import DynImport, read_config, tobool, reverse_lookup
import nipype.pipeline.engine as pe
from nipype import IdentityInterface
from pprint import pprint

#config.enable_debug_mode()
#logging.update_logging(config)

class DINGO(pe.Workflow):
    """Create a workflow from a json config file
    
    from DINGO.base import DINGO
    mywf = DINGO(configpath='/path/to/config.json')
    mywf.run()
    """
    
    workflow_to_module = {
        'SplitIDs'              :    'DINGO.wf',
        'SplitIDs_iterate'      :    'DINGO.wf',
        'FileIn'                :    'DINGO.wf',
        'FileIn_SConfig'        :    'DINGO.wf',
        'FileOut'               :    'DINGO.wf',
        'DICE'                  :    'DINGO.wf',
        'Reorient'              :    'DINGO.fsl',
        'EddyC'                 :    'DINGO.fsl',
        'BET'                   :    'DINGO.fsl',
        'DTIFIT'                :    'DINGO.fsl',
        'FLIRT'                 :    'DINGO.fsl',
        'ApplyXFM'              :    'DINGO.fsl',
        'FNIRT'                 :    'DINGO.fsl',
        'ApplyWarp'             :    'DINGO.fsl',
        'FSL_nonlinreg'         :    'DINGO.fsl',
        'TBSS_prereg'           :    'DINGO.fsl',
        'TBSS_reg_NXN'          :    'DINGO.fsl',
        'TBSS_postreg'          :    'DINGO.fsl',
        'DSI_SRC'               :    'DINGO.DSI_Studio',
        'REC_prep'              :    'DINGO.DSI_Studio',
        'DSI_REC'               :    'DINGO.DSI_Studio',
        'DSI_TRK'               :    'DINGO.DSI_Studio',
        'DSI_ANA'               :    'DINGO.DSI_Studio',
        'DSI_EXP'               :    'DINGO.DSI_Studio'
    }
    
    def __init__(self, workflow_to_module=None, configpath=None, name=None,\
    **kwargs):
        if name is None:
            name = 'DINGO'
        super(DINGO,self).__init__(name=name,**kwargs)
        self.keep_and_move_files()
        
        if workflow_to_module is not None:
            self.update_wf_to_mod_map(**workflow_to_module)
        
        if configpath is None:
            self.configpath = None
            print('run %s.create_wf_from_config() to add subworkflows'
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
        wf        :    String specifiying the workflow
        
        Returns
        -------
        module    :    Module str containing function that will create the workflow
        """
        try:
            return cls.workflow_to_module[wf]
        except KeyError:
            msg = 'Workflow: %s not associated with a module' % wf
            raise KeyError(msg)
    
    def keep_and_move_files(self):
        self.config['execution'] = {
            'use_relative_paths' : 'True',
            'remove_unnecessary_outputs' : 'False'
        }
                            
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
        
        
    def create_config_inputs(self, inputsname='Config_Inputs', **kwargs):
        prevci = self.get_node(inputsname)
        if prevci is not None:
            ci = prevci
            iterablelist = ci.iterables
            self.remove_nodes([prevci])
        else:
            ci = pe.Node(name=inputsname, 
                interface=IdentityInterface(
                    fields=kwargs.keys()))
            iterablelist = []
        
        for k,v in kwargs.iteritems():
            setattr(ci.inputs, k, v)
            if isinstance(v, list) and k != 'steps':
                for elt in iterablelist:
                    if k == elt[0]:#each elt a tuple of name, list
                        iterablelist.remove(elt)
                iterablelist.append((k,v))#position doesn't matter
            if len(iterablelist) > 0:
                setattr(ci, 'iterables', iterablelist)
                
        self.add_nodes([ci])
        self._inputsname = inputsname
        
    def create_subwf(self, step, name):
        """update subwf.inputs with self.input_params[subwfname]
        add subwf to self.subflows[subwfname]
        """
        _, obj = DynImport(mod=self.wf_to_mod(step), obj=step)
        ci = self.get_node(self._inputsname)
        for paramkey, paramval in self.input_params[name].iteritems():
            if isinstance(paramval, (str,unicode)) and \
            hasattr(ci.inputs, paramval):
                cival = getattr(ci.inputs, paramval)
                self.input_params[name].update({paramkey:cival})
        try:
            self.subflows[name] = obj(name=name, 
                inputs_name = self._inputsname, 
                inputs=self.input_params[name])
        except:
            print('#######Error######')
            pprint(self.input_params[name])
            raise
    
    def make_connection(self, srcobj, srcfield, destobj, destfield):
        """Connect srcfield and destfield, allow for nodes and workflows"""
        if issubclass(type(srcobj), pe.Node):
            srcname = (srcfield,)
        elif issubclass(type(srcobj), pe.Workflow):
            if hasattr(srcobj, '_outputnode') and \
            srcobj._outputnode is not None:
                srcname = (srcobj._outputnode, srcfield)
            else:
                srcname = ('outputnode', srcfield)
        srcname = '.'.join(srcname)
        
        if issubclass(type(destobj), pe.Node):
            destname = (destfield,)
        elif issubclass(type(destobj), pe.Workflow):
            if hasattr(destobj, '_inputnode') and \
            destobj._inputnode is not None:
                destname = (destobj._inputnode, destfield)
            else:
                destname = ('inputnode', destfield)
        destname = '.'.join(destname)
                    
        print('Connecting %s.%s --> %s.%s' %
            (srcobj.name, srcname, destobj.name, destname))
        self.connect(srcobj, srcname, destobj, destname)
        
    def _connect_subwfs(self):
        """update subwf.connection_spec with self.input_connections[subwfname]
        and connect subwfs
        
        Expects
        -------
        self.subflows[subwfname] = subwfobj
        self.input_connections[subwfname] = {'input':['src','output']}
        """
        self.workflow_connections = dict()
        for destkey, destobj in self.subflows.iteritems():
            try:
                #make sure repeat objs are not using the same dict
                destobj.connection_spec = destobj.connection_spec.copy()
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
                    srcobj = self.subflows[testsrckey]
                elif self.name2step.values().count(testsrckey) > 1:
                    raise Exception('Step: %s used more than once, default'
                        'connections will not work. Add ["method"]["Name"]'
                        '["connect"] for linked downstream nodes.' % testsrckey)
                elif testsrckey == 'Config' or testsrckey == self._inputsname:
                    srcobj = self.get_node(self._inputsname)
                else:
                    #testsrckey is step that appears once, name!=step
                    try:
                        srckey = reverse_lookup(self.name2step, testsrckey)
                        srcobj = self.subflows[srckey]
                    except ValueError:
                        print('destkey: %s' % destkey)
                        raise
                    
                #srcobj = self.subflows[srckey]
                self.make_connection(srcobj, srcfield, destobj, destfield)
        
            
    def create_wf_from_config(self, cfgpath, expected_keys=None):
        """Create and connect steps provided in json configuration file.
        
        Parameters
        ----------
        cfgpath            :    filepath to json configuration
        expected_keys    :    tuple pairs of keyname and expected type
            ('key', expected_type)
            (('key', expected_type), ('altkey', expected_type))
        
        Updates
        -------
        Nipype Workflow
        Node config_inputs[expected_keys]
            name                :    Str
            data_dir            :    Path
            included_ids        :    List[Str]
                included_ids['SubjectId_ScanId_UniqueID']
        input_params        :    Dict[Dict]
            input_params{subflowname{paramname:paramvalue}}
        input_connections    :    Dict[Dict[List[List]]]
            input_connections{subflowname{precedingflowname[[output,input]]}}
        subflows            :    Dict[Workflow/Node]
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
        print('Nipype cache at: %s' % os.path.join(self.base_dir,self.name))

        #Set up from config
        self.create_config_inputs(**input_fields)
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
                        ' Duplicates of Name: %s' % 
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
                                '["method"]["%s"]["connect"] Invalid config. '
                                'Key: %s, Value: %s' %
                                (cfg_bn, name, destfield, values))
                    self.input_connections[name] = connections
                else:
                    self.input_connections[name] = {}
            print('Create Workflow/Node Name:%s, Obj:%s' % (name, step))
            self.create_subwf(step, name)
        self._connect_subwfs()
        
        
class DINGOmeta(type):
    def __new__(mcls, name, bases, attrs):
        nipype_types = {
            'Workflow'   :    pe.Workflow, 
            'Node'       :    pe.Node, 
            'JoinNode'   :    pe.JoinNode, 
            'MapNode'    :    pe.MapNode
        }
        print('mcls: %s' % mcls)
        print('name: %s' % name)
        print(bases)
        print('attrs: %s' % attrs)
        if 'nipype_parent' in attrs.keys() and \
        attrs['nipype_parent'] is not None and \
        not any([v in bases for v in nipype_types.iteritems()]):
            newbases = (nipype_types[attrs['nipype_parent']],)
            return super(DINGOmeta, mcls).__new__(mcls, name, newbases, attrs)
        else:
            return super(DINGOmeta, mcls).__new__(mcls, name, bases, attrs)
        
        
class DINGObase(object):
#    __metaclass__ = DINGOmeta
    config_inputs = 'config_inputs'
    connection_spec = {}
    
    def __init__(self, connection_spec=None, inputs_name=None, 
#    nipype_parent=None, 
    **kwargs):
        
        if inputs_name is not None:
            self.config_inputs = inputs_name
            
        if connection_spec is not None:
            self.connection_spec.update(connection_spec)
            
#        if nipype_parent is not None:
#            self.nipype_parent = nipype_parent
    

class DINGOflow(pe.Workflow, DINGObase):
    """Add requisite properties to Nipype Workflow. Output folder 'Name', will 
    be in top level of nipype cache with its own parameterized iterables 
    folders.
    """
    _inputnode = None
    _outputnode = None
    
    def __init__(self, connection_spec=None, inputs_name=None, inputs=None,
    **kwargs):
        pe.Workflow.__init__(self, **kwargs)
        DINGObase.__init__(self,
            connection_spec=connection_spec,
            inputs_name=inputs_name)
            
            
class DINGOnode(pe.Node, DINGObase):
    """Add requisite properties to Nipype Node. Output folder 'Name', will be in
     the parameterized iterables folders.
     """
    
    def __init__(self, connection_spec=None, inputs_name=None, inputs=None,
    **kwargs):
        pe.Node.__init__(self, **kwargs)
        DINGObase.__init__(self, 
            connection_spec=connection_spec,
            inputs_name=inputs_name)
    
