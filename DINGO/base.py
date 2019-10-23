import os
import sys
import smtplib
from importlib import import_module
from email.mime.text import MIMEText
from collections import OrderedDict
from pprint import pprint
from nipype import config
from nipype.interfaces.base import Interface
import nipype.pipeline.engine as pe
from nipype import IdentityInterface
from DINGO.utils import (read_setup,
                         reverse_lookup,
                         tobool)


def keep_and_move_files():
    cfg = dict(execution={'remove_unnecessary_outputs': u'false'})
    config.update_config(cfg)


def check_input_field(setup_bn, setup, keyname, exptype):
    if keyname not in setup:
        raise KeyError('Analysis setup: {0}, missing required key ["{1}"]'
                       .format(setup_bn, keyname))
    elif not isinstance(setup[keyname], exptype):
        raise TypeError('Analysis setup: {0}, ["{1}"] is not a {2}'
                        'Type: {3}, Value: {4}'
                        .format(setup_bn, keyname, exptype,
                                type(setup[keyname]), setup[keyname]))


def check_input_fields(setup_bn, setup, expected_keys):
    """Loop through expected_keys
    Check if each 0th element has 1st element type
    """
    input_fields = {}
    alternatives = {}

    for keytuple in expected_keys:
        if isinstance(keytuple[0], (unicode, str)):
            keyname = keytuple[0]
            valtype = keytuple[1]
        elif isinstance(keytuple[0], (tuple, list)):
            # alternatives to check are subsequent elements
            # sublevel implies mutually inclusive alternatives
            keyname = keytuple[0][0]
            valtype = keytuple[0][1]
            alternatives.update({keytuple[0][0]: keytuple[1:]})
        else:
            msg = 'Unhandled pair: {0}, for Setup: {1}'.format(keytuple, setup_bn)
            raise TypeError(msg)
        try:
            check_input_field(setup_bn, setup, keyname, valtype)
            input_fields.update({keyname: setup[keyname]})
        except (KeyError, TypeError):
            if keyname in alternatives.keys():
                alt = alternatives[keyname]
                if isinstance(alt[0], (unicode, str)):
                    keyname = alt[0]
                    valtype = alt[1]
                    check_input_field(setup_bn, setup, keyname, valtype)
                    input_fields.update({keyname: setup[keyname]})
                elif isinstance(alt[0], (tuple, list)):
                    for altpair in alt:
                        keyname = altpair[0]
                        valtype = altpair[1]
                        check_input_field(setup_bn, setup, keyname, valtype)
                        input_fields.update({keyname: setup[keyname]})
            else:
                raise
    return input_fields


def dingo_node_factory(name=None, engine_type='Node', **kwargs):
    node_class = type(name,
                      (getattr(pe, engine_type),),
                      {})
    # cannot pickle class (failure on run) if not added to globals
    globals()[name] = node_class
    return node_class


class DINGONodeFlowBase(object):
    setup_inputs = 'setup_inputs'
    connection_spec = {}

    def __init__(self, connection_spec=None, inputs_name=None,
                 **kwargs):

        if inputs_name is not None:
            self.setup_inputs = inputs_name

        if connection_spec is not None:
            self.connection_spec.update(connection_spec)
            for k, v in connection_spec.items():
                if not v:  # v is an empty list
                    del connection_spec[k]


class DINGOFlow(pe.Workflow, DINGONodeFlowBase):
    """Add requisite properties to Nipype Workflow. Output folder 'Name', will
    be in top level of nipype cache with its own parameterized iterables
    folders.
    """
    inputnode = None
    outputnode = None

    def __init__(self, connection_spec=None, inputs_name=None, inputs=None,
                 **kwargs):
        pe.Workflow.__init__(self, **kwargs)
        DINGONodeFlowBase.__init__(self,
                                   connection_spec=connection_spec,
                                   inputs_name=inputs_name)


class DINGONode(pe.Node, DINGONodeFlowBase):
    """Add requisite properties to Nipype Node. Output folder 'Name', will be in
     the parameterized iterables folders.
     """

    def __init__(self, connection_spec=None, inputs_name=None, inputs=None,
                 **kwargs):
        pe.Node.__init__(self, **kwargs)
        DINGONodeFlowBase.__init__(self,
                                   connection_spec=connection_spec,
                                   inputs_name=inputs_name)


class DINGO(pe.Workflow):
    """Create a workflow from a json setup file

    from DINGO.base import DINGO
    mywf = DINGO(setuppath='/path/to/setup.json')
    mywf.run()
    """

    workflow_to_module = {
        'SplitIDs':         'DINGO.workflows.utils',
        'SplitIDsIterate':  'DINGO.workflows.utils',
        'FileIn':           'DINGO.workflows.utils',
        'FileInSConfig':    'DINGO.workflows.utils',
        'FileOut':          'DINGO.workflows.utils',
        'DICE':             'DINGO.workflows.utils',
        'Reorient':         'DINGO.workflows.fsl',
        'EddyC':            'DINGO.workflows.fsl',
        'BET':              'DINGO.workflows.fsl',
        'DTIFIT':           'DINGO.workflows.fsl',
        'FLIRT':            'DINGO.workflows.fsl',
        'ApplyXFM':         'DINGO.workflows.fsl',
        'FNIRT':            'DINGO.workflows.fsl',
        'ApplyWarp':        'DINGO.workflows.fsl',
        'FSLNonLinReg':     'DINGO.workflows.fsl',
        'TBSSPreReg':       'DINGO.workflows.fsl',
        'TBSSRegNXN':       'DINGO.workflows.fsl',
        'TBSSPostReg':      'DINGO.workflows.fsl',
        'DSI_SRC':          'DINGO.workflows.dsistudio',
        'REC_prep':         'DINGO.workflows.dsistudio',
        'DSI_REC':          'DINGO.workflows.dsistudio',
        'DSI_TRK':          'DINGO.workflows.dsistudio',
        'DSI_ANA':          'DINGO.workflows.dsistudio',
        'DSI_Merge':        'DINGO.workflows.dsistudio',
        'DSI_EXP':          'DINGO.workflows.dsistudio'
    }

    def __init__(self, setuppath=None, workflow_to_module=None, name=None,
                 **kwargs):
        self.email = None
        self._inputsname = None
        self.name2step = dict()
        self.input_connections = dict()
        self.input_params = dict()
        self.subflows = OrderedDict()
        if name is None:
            name = 'DINGO'

        keep_and_move_files()
        super(DINGO, self).__init__(name=name, **kwargs)

        if workflow_to_module is not None:
            self.update_wf_to_mod_map(**workflow_to_module)

        if setuppath is None:
            self.setuppath = None
            print('run {}.create_wf_from_setup() to add subworkflows'
                  .format(self))
        else:
            self.setuppath = setuppath
            self.create_wf_from_setup(setuppath)

    def update_wf_to_mod_map(self, **updates):
        self.workflow_to_module.update(**updates)

    @classmethod
    def wf_to_mod(cls, wf):
        """Get module containing func for creation given nipype workflow name

        Parameters
        ----------
        wf        :    String specifying the workflow

        Returns
        -------
        module    :    Module str containing function that will create the workflow
        """
        try:
            return cls.workflow_to_module[wf]
        except KeyError:
            msg = 'Workflow: {} not associated with a module'.format(wf)
            raise KeyError(msg)

    def create_setup_inputs(self, inputsname='Setup_Inputs', **kwargs):
        previous_setup = self.get_node(inputsname)
        if previous_setup is not None:
            setup = previous_setup
            iterable_list = setup.iterables
            self.remove_nodes([previous_setup])
        else:
            setup = pe.Node(name=inputsname,
                            interface=IdentityInterface(
                                fields=kwargs.keys()))
            iterable_list = []

        for k, v in kwargs.iteritems():
            setattr(setup.inputs, k, v)
            if isinstance(v, list) and k != 'steps':
                for elt in iterable_list:
                    if k == elt[0]:  # each elt a tuple of name, list
                        iterable_list.remove(elt)
                iterable_list.append((k, v))  # position doesn't matter
            if len(iterable_list) > 0:
                setattr(setup, 'iterables', iterable_list)

        self.add_nodes([setup])
        self._inputsname = inputsname

    def import_mod_obj(self, my_string):
        try:
            mod_string, obj_string = my_string.rsplit('.', 1)
            mod = import_module(mod_string)
            obj = getattr(mod, obj_string)
        # catch string split error, try workflow name to module map
        # pass ImportError, AttributeError
        except ValueError:
            mod = import_module(self.wf_to_mod(my_string))
            obj = getattr(mod, my_string)
        return mod, obj

    def create_subwf(self, step, name):
        """update subwf.inputs with self.input_params[subwfname]
        add subwf to self.subflows[subwfname]
        """
        setup = self.get_node(self._inputsname)
        for paramkey, paramval in self.input_params[name].iteritems():
            if isinstance(paramval, (str, unicode)) and \
                    hasattr(setup.inputs, paramval):
                setup_val = getattr(setup.inputs, paramval)
                self.input_params[name].update({paramkey: setup_val})
        _, obj = self.import_mod_obj(step)
        try:
            if issubclass(obj, Interface):
                new_class = dingo_node_factory(name=name,
                                               interface=obj,
                                               **self.input_params[name])
                self.subflows[name] = new_class(name=name, interface=obj(**self.input_params[name]))
            else:
                self.subflows[name] = obj(name=name,
                                          inputs_name=self._inputsname,
                                          inputs=self.input_params[name])
        except Exception:
            print('#######Error######')
            pprint(self.input_params[name])
            raise

    def make_connection(self, srcobj, srcfield, destobj, destfield):
        """Connect srcfield and destfield, allow for nodes and workflows"""
        if issubclass(type(srcobj), pe.Node):
            srcname = (srcfield,)
        elif issubclass(type(srcobj), pe.Workflow):
            if hasattr(srcobj, 'outputnode') and \
                    srcobj.outputnode is not None:
                srcname = (srcobj.outputnode, srcfield)
            else:
                srcname = ('outputnode', srcfield)
        else:
            msg = ('Unexpected class: {} for {}. '
                   'Should subclass one of (Node, Workflow)'
                   .format(type(srcobj), srcfield))
            raise TypeError(msg)
        srcname = '.'.join(srcname)
        if issubclass(type(destobj), pe.Node):
            destname = (destfield,)
        elif issubclass(type(destobj), pe.Workflow):
            if hasattr(destobj, 'inputnode') and \
                    destobj.inputnode is not None:
                destname = (destobj.inputnode, destfield)
            else:
                destname = ('inputnode', destfield)
        destname = '.'.join(destname)

        print('Connecting {}.{} <- {}.{}'.format(
            destobj.name, destname, srcobj.name, srcname))
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
                # make sure repeat objs are not using the same dict
                destobj.connection_spec = destobj.connection_spec.copy()
                destobj.connection_spec.update(
                    self.input_connections[destkey])
            except AttributeError:
                # simple attempt to support non DINGO
                destobj.connection_spec = {}
                destobj.connection_spec.update(
                    self.input_connections[destkey])

            self.workflow_connections[destkey] = destobj.connection_spec
            for destfield, values in \
                    self.workflow_connections[destkey].iteritems():
                if len(values) == 2:
                    testsrckey = values[0]
                    srcfield = values[1]
                elif len(values) == 0:  # to blank a default connection
                    continue
                else:
                    msg = ('Connection spec for {}.{} malformed. Should be '
                           '[SourceObj, SourceKey], or [] to supersede default.'
                           ' but is: {} '.format(destkey, destfield, values))
                    raise (ValueError(msg))

                if testsrckey in self.name2step:
                    # connection from setup, or at least name==step
                    srcobj = self.subflows[testsrckey]
                elif self.name2step.values().count(testsrckey) > 1:
                    msg = ('Destination: {0}.{1}, "{2}" used more than once, default '
                           'connections will not work. Add ["method"]["{0}"]'
                           '["connect"]["{1}"] to json to set connection.'
                           .format(destkey, destfield, testsrckey))
                    raise Exception(msg)
                elif (testsrckey == self._inputsname or
                      testsrckey.lower() == 'setup' or
                      testsrckey.lower() == 'config'):
                    srcobj = self.get_node(self._inputsname)
                else:
                    # testsrckey is step that appears once, name!=step
                    try:
                        srckey = reverse_lookup(self.name2step, testsrckey)
                        srcobj = self.subflows[srckey]
                    except ValueError:
                        print('destination_key: {}, destination_field: {}'
                              .format(destkey, destfield))
                        raise

                self.make_connection(srcobj, srcfield, destobj, destfield)

    def create_wf_from_setup(self, setuppath, expected_keys=None):
        """Create and connect steps provided in json setup file.
        
        Parameters
        ----------
        setuppath            :    filepath to json setup
        expected_keys    :    tuple pairs of keyname and expected type
            ('key', expected_type)
            (('key', expected_type), ('altkey', expected_type))
        
        Updates
        -------
        Nipype Workflow
        Node setup_inputs[expected_keys]
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

        # Read setup file
        if setuppath is None:
            raise NameError('Required setuppath unspecified')
        setup = read_setup(setuppath)
        setup_bn = os.path.basename(setuppath)

        # Check important setup keys
        if expected_keys is None:
            expected_keys = (
                ('name', (unicode, str)),
                ('data_dir', (unicode, str)),
                ('steps', list),
                ('method', dict),
                (('included_ids', list), (
                    ('included_imgs', list), ('included_masks', list)))
            )
        # expected keynames should be top level fields in the configuration
        input_fields = check_input_fields(setup_bn, setup, expected_keys)
        if 'data_dir' in input_fields:
            self.base_dir = input_fields['data_dir']
        if 'name' in input_fields:
            self.name = input_fields['name']
        os.chdir(self.base_dir)
        print('Nipype cache at: {}'.format(
              os.path.join(self.base_dir, self.name)))

        # Set up from configuration
        self.create_setup_inputs(**input_fields)

        if 'email' in setup:
            self.email = setup['email']

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
            self.name2step.update({name: step})
            # Get changes to defaults from setup file
            # Checking types to give informative error messages
            if not isinstance(step, (str, unicode, list)):
                raise TypeError('Analysis Setup: {0}, Invalid configuration.\n'
                                'Step: {1}, of type "{3}", named {2} '
                                'is not str or unicode, '
                                'or list ["module", "object"]'
                                .format(setup_bn, step, name, type(step)))
            if not isinstance(name, (str, unicode)):
                raise TypeError('Analysis Setup: {0}, Invalid configuration.\n'
                                'Name: {2}, of type "{3}", for step {2} '
                                'is not str or unicode'
                                .format(setup_bn, step, name, type(name)))
            if name in self.subflows:
                raise KeyError('Analysis Setup: {0}, Invalid configuration.'
                               ' Duplicates of Name: {1}'
                               .format(setup_bn, name))
            if name in method and 'inputs' in method[name]:
                # inputs are flags for the function creating the workflow
                # used in various fashions
                inputs = method[name]['inputs']
                if not isinstance(inputs, dict):
                    raise TypeError('Analysis Setup: {0}, Invalid configuration '
                                    '["method"]["{1}"]["inputs"] is not a dict. '
                                    'Value: {2}, Type: {3}'
                                    .format(setup_bn, name, inputs, type(inputs)))
                self.input_params[name] = inputs
            else:
                self.input_params[name] = {}
                print('### No input params found for {}, using defaults ###'
                      .format(name))
            if name in method and 'connect' in method[name]:
                # connect given by { "input": ["Source Node", "output"]}
                connections = method[name]['connect']
                if not isinstance(connections, dict):
                    raise TypeError('Analysis Setup: {0}, Invalid configuration '
                                    '["method"]["{1}"]["connect"] is not a dict. '
                                    'Value: {2}, Type: {3}'
                                    .format(setup_bn, name, connections, type(connections)))
                for destfield, values in connections.iteritems():
                    if not isinstance(destfield, (str, unicode)) or \
                            not isinstance(values, (list, tuple)):
                        raise TypeError('Analysis Setup: {0}, Invalid configuration '
                                        '["method"]["{1}"]["connect"], '
                                        'Key: {2}, Value: {3}'
                                        .format(setup_bn, name, destfield, values))
                self.input_connections[name] = connections
            else:
                self.input_connections[name] = {}
                print('### No input connections found for {}, using defaults ###'
                      .format(name))
            print('Create Workflow/Node Name:{0}, Obj:{1}'.format(name, step))
            self.create_subwf(step, name)
        self._connect_subwfs()
        if self.email is not None:
            print('Email notification will be sent to {}'
                  .format(self.email['toaddr']))
        else:
            print('No email notification will be sent')

    def send_mail(self, msg_body=None):
        """Send a notification for workflow conclusion
        
        Parameters
        -------
        self.email      :   dictionary
            server      :   str 'server:port'
            login       :   str
            pw          :   str
            fromaddr    :   str
            toaddr      :   str
        msg_body        :   str
        """
        if 'server' not in self.email or self.email['server'] is None:
            self.email['server'] = 'localhost'

        s = smtplib.SMTP(self.email['server'])

        msg = MIMEText(msg_body)
        msg['Subject'] = 'DINGO workflow completed'
        msg['From'] = self.email['fromaddr']
        msg['To'] = self.email['toaddr']

        if 'login' in self.email and self.email['login'] is not None \
                and 'pw' in self.email and self.email['pw'] is not None:
            s.starttls()
            s.login(self.email['login'], self.email['pw'])

        s.sendmail(self.email['fromaddr'], self.email['toaddr'], msg.as_string())

    def run(self, plugin=None, plugin_args=None, updatehash=False):
        """Execute the workflow
        
        Parameters
        ----------
        plugin      :   plugin name or object
            Plugin to use for execution. You can create your own plugins for
            execution.
        plugin_args :   dictionary containing arguments to be sent to plugin
            constructor. see individual plugin doc strings for details.
        self.email  :   dictionary containing arguments to send a notification
            upon completion.
        """
        try:
            super(DINGO, self).run(
                plugin=plugin, plugin_args=plugin_args, updatehash=updatehash)
            msg = '{} completed without error'.format(self.name)
        except RuntimeError:
            msg = '{} ended with error(s)'.format(self.name)
            raise
        except Exception:
            msg = '{} crashed'.format(self.name)
            raise
        finally:
            if self.email is not None:
                msg_list = []
                msg_list.extend((msg, 'With named steps:'))
                msg_list.extend(self.subflows.keys())
                self.send_mail(msg_body='\n'.join(msg_list))


if __name__ == '__main__':
    print(sys.argv[1])
    run_args = dict()
    if 'plugin' in sys.argv:
        plugin = sys.argv[sys.argv.index('plugin')+1]
    else:
        plugin = 'Linear'
    run_args.update(plugin=plugin)
    if 'plugin_args' in sys.argv:
        plugin_args_k = sys.argv[sys.argv.index('plugin_args')+1::2]
        plugin_args_v = sys.argv[sys.argv.index('plugin_args')+2::2]
        for i in range(len(plugin_args_v)):
            if plugin_args_v[i].isdigit():
                plugin_args_v[i] = int(plugin_args_v[i])
            else:
                try:
                    plugin_args_v[i] = tobool(plugin_args_v[i])
                except ValueError: # not accepted boolean repr
                    pass
        if len(plugin_args_k) == len(plugin_args_v):
            plugin_args = dict()
            for i in range(0, len(plugin_args_k)):
                plugin_args.update({plugin_args_k[i]: plugin_args_v[i]})
        else:
            raise(SyntaxError('Number of plugin_args keys does not match number'
                              ' of plugin_args values'))
        run_args.update(plugin_args=plugin_args)
    pprint(run_args)
    workflow = DINGO(sys.argv[1])
    workflow.run(**run_args)
