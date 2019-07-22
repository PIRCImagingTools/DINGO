import os
from DINGO.utils import (read_setup,
                         split_chpid,
                         join_strs,
                         tobool)
from DINGO.base import (DINGO,
                        DINGOFlow,
                        DINGONode)
from nipype import (IdentityInterface,
                    Function)
import nipype.pipeline.engine as pe
import nipype.interfaces.io as nio
from nipype.pipeline.engine.utils import _parameterization_dir
from tempfile import mkdtemp


class HelperFlow(DINGO):
    
    def __init__(self, workflow_to_module=None, **kwargs):
        wfm = {
            'SplitIDs':         'DINGO.workflows.utils',
            'SplitIDsIterate':  'DINGO.workflows.utils',
            'FileIn':           'DINGO.workflows.utils',
            'FileInSConfig':    'DINGO.workflows.utils',
            'FileOut':          'DINGO.workflows.utils',
            'DICE':             'DINGO.workflows.utils'
        }
        
        if workflow_to_module is None:
            workflow_to_module = wfm
        else:
            for k, v in wfm.iteritems():
                if k not in workflow_to_module:
                    workflow_to_module.update({k: v})
        
        super(HelperFlow, self).__init__(
            workflow_to_module=workflow_to_module,
            **kwargs
        )


class TRKnode(pe.Node):
    """Replace extended iterable parameterization with simpler based on
    just id and tract_name, not tract_inputs
    """

    @staticmethod
    def tract_name_dir(param):
        """Return a reduced parameterization for output directory"""
        if '_tract_names' in param:
            return param[param.index('_tract_names'):]
        return param

    def output_dir(self):
        """Return the location of the output directory with tract name,
        not tract inputs
        Mostly the same as nipype.pipeline.engine.Node.output_dir"""
        if self._output_dir:
            return self._output_dir

        if self.base_dir is None:
            self.base_dir = mkdtemp()
        outputdir = self.base_dir
        if self._hierarchy:
            outputdir = os.path.join(outputdir, *self._hierarchy.split('.'))
        if self.parameterization:
            params_str = ['{}'.format(p) for p in self.parameterization]
            params_str = [TRKnode.tract_name_dir(p) for p in params_str]
            if not tobool(self.config['execution']['parameterize_dirs']):
                params_str = [_parameterization_dir(p) for p in params_str]
            outputdir = os.path.join(outputdir, *params_str)

        self._output_dir = os.path.abspath(os.path.join(outputdir, self.name))
        return self._output_dir


class TRKjoinnode(pe.JoinNode, TRKnode):
    def __init__(self, **kwargs):
        super(TRKjoinnode, self).__init__(**kwargs)


class DICE(DINGOFlow):
    """Nipype node to output dice image and coefficient for lists of niftis
    
    Inputs
    ------
    inputnode.nii_list_A
    inputnode.nii_list_B
    inputnode.tract_names - so that nifti lists don't have to be guaranteed to 
        match this parameter is used to search the filename and pass match on
    inputnode.sub_id
    inputnode.scan_id
    inputnode.uid
    inputnode.template - filename template
    inputnode.template_args - arguments to format filename template
    
    Outputs
    -------
    dicenode.dice
    dicenode.coef_file
    dicenode.img
    """
    inputnode = 'inputnode'
    outputnode = 'dicenode'
    connection_spec = {
        'sub_id':   ['SplitIDs', 'sub_id'],
        'scan_id':  ['SplitIDs', 'scan_id'],
        'uid':      ['SplitIDs', 'uid']
    }
    
    def __init__(self, name='DICE', inputs=None, **kwargs):
        super(DICE, self).__init__(name=name, **kwargs)

        input_iters = ('tract_names', inputs['tract_names'])
        
        inputnode = pe.Node(
            name='inputnode',
            interface=IdentityInterface(fields=[elt for elt in inputs]),
            iterables=input_iters)
            
        for elt in inputs:
            if elt is not None:
                setattr(inputnode.inputs, elt, inputs[elt])
        
        get_tracts = pe.Node(
            name='get_tracts',
            interface=Function(
                input_names=['tract_name', 'tract_list_a', 'tract_list_b'],
                output_names=['tract_a', 'tract_b'],
                function=self.get_tracts))
        
        dicenode = pe.Node(
            name='dicenode',
            interface=Function(
                input_names=['nii_a', 'nii_b', 'output_bn'],
                output_names=['img', 'coef'],
                function=self.dice_coef))
        
        create_bn = pe.Node(
            name='create_bn',
            interface=Function(
                input_names=['template',
                             'template_args',
                             'tract_name',
                             'subid', 'scanid', 'uid'],
                output_names=['file'],
                function=self.create_basename))
                
        # Connect
        self.connect([
            (inputnode, get_tracts, [
                ('nii_list_a', 'tract_list_a'),
                ('nii_list_b', 'tract_list_b'),
                ('tract_names', 'tract_name')]),
            (inputnode, create_bn, [
                ('template', 'template'),
                ('template_args', 'template_args'),
                ('tract_name', 'tract_name'),
                ('sub_id', 'subid'),
                ('scan_id', 'scanid'),
                ('uid', 'uid')]),
            (get_tracts, dicenode, [
                ('tract_a', 'nii_a'),
                ('tract_b', 'nii_b')]),
            (create_bn, dicenode, [
                ('file', 'output_bn')])
        ])

    def get_tracts(tract_name, tract_list_a, tract_list_b):
        """Takes a list of tract file strings and single tract name, returns
        the matching tract from list

        tract_list = ['path/to/..._tract_name0.trk...',
                      '/path/to/tract_name1.trk...']
        tract_name = 'tract_name1'
        tract = get_tract(tract_list, tract_name)
        tract -> '/path/to/tract_name1.trk...'
        
        Will raise if tract not matched, or more than one match.
        """
        import re
        import os
        from nipy import load_image, save_image
        from nipy.testing import anatfile
        import numpy as np
        from nipy.core.api import Image
        # tract name preceded by '\', '_', '\'
        tract_a = None
        tract_b = None
        pattern = ''.join(('(?<=[\\\\_\/])(?P<tract>', tract_name, ')'))
        comp = re.compile(pattern)
        err_msg = 'More than one tract found matching "{}" in list "{}"'
        search_a = [re.search(comp, t) for t in tract_list_a]
        tractsearch_a = filter(lambda x: x is not None, search_a)
        if len(tractsearch_a) == 1:
            index_a = search_a.index(tractsearch_a[0])
            tract_a = tract_list_a[index_a]
        elif len(tractsearch_a) > 1:
            raise LookupError(err_msg.format(pattern, 'A'))
        search_b = [re.search(comp, t) for t in tract_list_b]
        tractsearch_b = filter(lambda x: x is not None, search_b)
        if len(tractsearch_b) == 1:
            index_b = search_b.index(tractsearch_b[0])
            tract_b = tract_list_b[index_b]
        elif len(tractsearch_b) > 1:
            raise LookupError(err_msg.format(pattern, 'B'))
        if tract_a is None and tract_b is not None:
            img_b = load_image(tract_b)
            new_img = Image(np.zeros(img_b.shape), img_b.coordmap)
            tract_a = save_image(new_img, os.path.join(os.getcwd(), 'empty_a'))
        elif tract_a is not None and tract_b is None:
            img_a = load_image(tract_a)
            new_img = Image(np.zeros(img_a.shape), img_a.coordmap)
            tract_b = save_image(new_img, os.path.join(os.getcwd(), 'empty_b'))
        else:
            test_img = load_image(anatfile)
            full_img = Image(np.ones(test_img.shape), test_img.coordmap)
            tract_a = save_image(full_img, os.path.join(os.getcwd(), 'empty_a'))
            tract_b = save_image(full_img, os.path.join(os.getcwd(), 'empty_b'))
        return tract_a, tract_b
    
    def create_basename(template=None,
                        template_args=None,
                        **kwargs):
        """Takes a template string and template_args, returns formatted string.
        
        Parameters
        ------
        template        :   Str - format string, default 'DICE_{0}_{1}_{2}_{3}.txt'
        template_args   :   Seq - input arguments for formatting,
                             default: ('tract_name', 'subid', 'scanid', uid')
        
        Returns
        -------
        basename        :   Str - formatted string

        """
        from nipype.interfaces.base import isdefined
        if not isdefined(template) or template is None:
            template = 'DICE_{0}_{1}_{2}_{3}.txt'
        if not isdefined(template_args) or template_args is None:
            template_args = ('tract_name',
                             'subid',
                             'scanid',
                             'uid')
        strings = [kwargs[k] for k in template_args]
        return template.format(*strings)

    def dice_coef(nii_a, nii_b, output_bn):
        """
        Dice Coefficient:
            D = 2*(A == B)/(A)+(B)
        
        Input is two binary masks in the same 3D space
        NII format
        
        Output is a DICE score and overlap image
        """
        # imports in function for nipype
        from nipy import load_image, save_image
        import numpy as np
        from nipy.core.api import Image
        import os
        
        image_a = load_image(nii_a)
        data_a = image_a.get_data()
        sum_a = np.sum(data_a)
        coord = image_a.coordmap

        image_b = load_image(nii_b)
        data_b = image_b.get_data()
        sum_b = np.sum(data_b)
        
        overlap = data_a + data_b
        intersect = overlap[np.where(overlap == 2)].sum()
        
        dice = intersect/(sum_a + sum_b)
        
        def save_nii(data, coord, save_file):
            save_path = os.path.join(os.getcwd(), save_file)
            arr_img = Image(data, coord)
            img = save_image(arr_img, save_path)
            return img
            
        def save_txt(dice, save_file_bn):
            save_file = os.path.join(os.getcwd(), save_file_bn)
            with open(save_file, 'w') as f:
                f.write('{0}'.format(dice))
            return save_file
        
        img = save_nii(overlap, coord, output_bn)
        coef_file = save_txt(dice, output_bn)
        return dice, coef_file, img


class SplitIDs(DINGONode):
    """Nipype node to split a CHP_ID into separate subject, scan and task ids
    
    Parameters
    ----------
    name            :    Str (workflow name, default 'SplitIDs')
    inputs          :    Dict
        parent_dir  :    Directory (base directory)
        id          :    Str
        id_sep      :    Str (default '_')
    kwargs          :    Nipype Node Kwargs
    
    Node Inputs
    -----------
    psid            :    Str
    sep             :    Str
    
    Node Outputs
    ------------
    sub_id          :    Str
    scan_id         :    Str
    uid             :    Str
    """
    
    connection_spec = {
        'psid': ['Config', 'included_ids']
    }
    
    def __init__(self,
                 name='SplitIDs',
                 inputs={'parent_dir': None,
                         'id': None,
                         'id_sep': '_'},
                 **kwargs):
        
        if 'parent_dir' in inputs and inputs['parent_dir'] is not None:
            self.base_dir = inputs['parent_dir']
            
        super(SplitIDs, self).__init__(
            name=name,
            interface=Function(
                input_names=['psid', 'sep'],
                output_names=['sub_id', 'scan_id', 'uid'],
                function=split_chpid),
            **kwargs)
            
        if 'id' in inputs and inputs['id'] is not None:
            self.inputs.psid = inputs['id']
        if 'id_sep' in inputs and inputs['id_sep'] is not None:
            self.inputs.sep = inputs['id_sep']
            
            
class SplitIDsIterate(DINGOFlow):
    """Nipype node to iterate a list of ids into separate subject, scan, and
    task ids.
    
    Parameters
    ----------
    name                :    Str (workflow name, default 'SplitIDs')
    inputs              :    Dict
        parent_dir      :    Directory (base directory)
        scan_list       :    List[Str] 
        scan_list_sep   :    Str (separator for fields in id)
    kwargs              :    Nipype Workflow Kwargs
        
    e.g. split_ids = create_split_ids(name='split_ids', 
                parent_dir=os.getcwd(),
                scan_list=[0761_MR1_42D_DTIFIXED,CHD_052_01a_DTIFIXED],
                sep='_')
        
    Returns
    -------
    splitids    :    Nipype workflow
    (splitids.outputnode.outputs=['sub_id', 'scan_id', 'uid'])
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
    inputnode = 'inputnode'
    outputnode = 'outputnode'
    
    def __init__(self, name='SplitIDs',
                 inputs={'parent_dir': None,
                         'scan_list': None,
                         'scan_list_sep': '_'},
                 **kwargs):
        
        super(SplitIDsIterate, self).__init__(name=name, **kwargs)
        
        # Create Workflow
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
            print("{}.inputnode.scan_list must be set before running"
                  .format(name))
            
        if 'scan_list_sep' in inputs and inputs['scan_list_sep'] is not None:
            inputnode.inputs.scan_list_sep = inputs['scan_list_sep']
        else:
            print("{}.inputnode.scan_list_sep must be set before running"
                  .format(name))

        splitidsnode = pe.Node(
            name="splitidsnode",
            interface=Function(
                input_names=["psid", "sep"],
                output_names=["sub_id", "scan_id", "uid"],
                function=split_chpid))
            
        outputnode = pe.Node(
            name="outputnode",
            interface=IdentityInterface(
                fields=["sub_id",
                        "scan_id",
                        "uid"],
                mandatory_inputs=True))
                
        # Connect workflow
        self.connect([
            (inputnode, splitidsnode, 
                [("scan_list", "psid"),
                 ("scan_list_sep", "sep")]),
            (splitidsnode, outputnode, 
                [("sub_id", "sub_id"),
                 ("scan_id", "scan_id"),
                 ("uid", "uid")])
            ])
    
    
class FileIn(DINGONode):
    """
    Parameters
    ----------
    name            :    Workflow name
    infields        :    List, template field arguments
        (default ['sub_id', 'scan_id', 'uid'])
    outfields       :    List, output files 
        (default ['nifti'])
    exts            :    Dict, extensions for output files
        (default {'nifti':'.nii.gz'}, only used if field_template 
        unspecified for outfield, and template ends in .ext)
    template        :    Str, default template
        (default '%s/%s/%s_%s_%s.ext')
    field_template  :    Dict, overwrite default template per outfield
    template_args   :    Dict, linking infields to template or field_template
    sort_filelist   :    Boolean
    
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
        'sub_id':   ['SplitIDs', 'sub_id'],
        'scan_id':  ['SplitIDs', 'scan_id'],
        'uid':      ['SplitIDs', 'uid']
    }
    
    def __init__(self,
                 name='FileIn',
                 inputs={'infields': None,
                         'outfields': None,
                         'exts': None,
                         'template': None,
                         'field_template': None,
                         'template_args': None,
                         'sort_filelist': True},
                 **kwargs):
    
        # Defaults
        if 'infields' not in inputs or inputs['infields'] is None:
            infields = ['sub_id', 'scan_id', 'uid']
        else:
            infields = inputs['infields']
        if 'exts' not in inputs or inputs['exts'] is None:
            exts = {'nifti': '.nii.gz'}
        else:
            exts = inputs['exts']
        if 'outfields' not in inputs or inputs['outfields'] is None:
            outfields = ['nifti']
        else:
            outfields = inputs['outfields']
        if 'template' not in inputs or inputs['template'] is None:
            template = '%s/%s/%s_%s_%s.ext'
        else:
            template = inputs['template']
        if 'sort_filelist' not in inputs or inputs['sort_filelist'] is None:
            sort_filelist = True
        else:
            sort_filelist = inputs['sort_filelist']
        if 'base_directory' not in inputs or inputs['base_directory'] is None:
            base_directory = os.getcwd()
        else:
            base_directory = inputs['base_directory']

        if ('field_template' not in inputs or
                inputs['field_template'] is None or
                len(inputs['field_template']) != len(outfields)):
            if len(outfields) != len(exts):
                raise ValueError('len(outfields): {:d} != len(ext) {:d}'
                                 .format(len(outfields), len(exts)))
            field_template = dict()
            for i in range(0, len(outfields)):
                field_template.update(
                    {outfields[i]: template.replace('.ext', exts[outfields[i]])})
        else:
            field_template = inputs['field_template']
            outfields = field_template.keys()
            
        if 'template_args' not in inputs or inputs['template_args'] is None:
            template_args = dict()
            for i in range(0, len(outfields)):
                template_args.update(
                    {outfields[i]:
                        [['sub_id', 'scan_id', 'sub_id', 'scan_id', 'uid']]})
        else:
            template_args = inputs['template_args']
            
        # Create DataGrabber node
        super(FileIn, self).__init__(name=name, 
                                     interface=nio.DataGrabber(
                                         infields=infields,
                                         outfields=outfields),
                                     **kwargs)
            
        self.inputs.base_directory = base_directory
        self.inputs.template = '*'
        self.inputs.field_template = field_template
        self.inputs.template_args = template_args
        self.inputs.sort_filelist = sort_filelist
    
    
class FileInSConfig(DINGOFlow):
    """Nipype workflow to get files specified in a subject config.json
    
    Mandatory Inputs - either in dict arg inputs or connected to inputnode
    ----------------
    base_directory  :    Str
    outfields       :    List[Str]
    sub_id          :    Str
    scan_id         :    Str
    uid             :    Str
    
    Optional Inputs - in dict arg inputs or connected to create_ft
    ---------------
    repl                :    List or Dict
    """
    inputnode = 'inputnode'
    outputnode = 'filein'
    
    connection_spec = {
        'sub_id':   ['SplitIDs', 'sub_id'],
        'scan_id':  ['SplitIDs', 'scan_id'],
        'uid':      ['SplitIDs', 'uid']
    }
    
    def __init__(self,
                 name='FileIn_SConfig',
                 inputs=None,
                 **kwargs):
        if inputs is None:
            inputs = {}
        super(FileInSConfig, self).__init__(name=name, **kwargs)
        
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
            raise KeyError('inputs["outfields"] '
                           'must be specified to instantiate {}'
                           .format(self.__class__))
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
                input_names=['setuppath'],
                output_names=['setupdict'],
                function=read_setup))
                
        create_ft = pe.Node(
            name='create_field_template',
            interface=Function(
                input_names=[
                    'base_directory',
                    'sub_id',
                    'scan_id',
                    'uid',
                    'config',
                    'outfields',
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
            (inputnode, cfgpath, [('base_directory', 'base_directory'),
                                  ('sub_id', 'sub_id'),
                                  ('scan_id', 'scan_id'),
                                  ('uid', 'uid')]),
            (inputnode, create_ft, [('base_directory', 'base_directory'),
                                    ('sub_id', 'sub_id'),
                                    ('scan_id', 'scan_id'),
                                    ('uid', 'uid'),
                                    ('outfields', 'outfields')]),
            (inputnode, filein, [('base_directory', 'base_directory')]),
            (cfgpath, read_conf, [('path', 'setuppath')]),
            (read_conf, create_ft, [('setupdict', 'config')]),
            (create_ft, filein, [('field_template', 'field_template')])
            ])

    def cfgpath_from_ids(base_directory=None,
                         sub_id=None, scan_id=None, uid=None):
        if (base_directory is not None and
                sub_id is not None and
                scan_id is not None and
                uid is not None):
            import os
            cfgname = []
            cfgname.extend((sub_id, scan_id, uid, 'config.json'))
            cfgname = '_'.join(cfgname)
            return os.path.join(base_directory, sub_id, scan_id, cfgname)
            
    def create_field_template(base_directory=None,
                              sub_id=None, scan_id=None, uid=None,
                              config=None, outfields=None, repl=None):
        import os
        defrepl = {
            'pid':          sub_id,
            'scanid':       scan_id,
            'sequenceid':   uid,
            'parent_dir':   base_directory
        }
        # defrepl will always be checked for substitution
        # compare (error sanity check) to config
        for k, v in defrepl.iteritems():
            if config[k] != v:
                raise Exception('Subject config error[{}]: '
                                'Expecting {}, Got {}'
                                .format(k, v, config[k]))
        
        # get values from config
        myrepl = dict()
        if repl is not None:
            if isinstance(repl, (str, unicode)):
                myrepl.update({repl: config['paths'][repl]})
                repl = list(repl)
            elif isinstance(repl, (list, tuple)):
                for e in repl:
                    myrepl.update({e: config['paths'][e]})
            elif isinstance(repl, dict):
                myrepl = repl
                repl = repl.keys()
                
            # value substitution of placeholders
            for e in repl:  # repl must be in most to least dependent order
                for mk, mv in myrepl.iteritems():
                    if e in mv:
                        myrepl.update({mk: mv.replace(e, myrepl[e])})
                                
        # create field template dict
        field_template = dict()
        for o in outfields:
            # add dir to outfield not repl so it's not duplicated
            value = config['paths'][o]
            dirkey = '_'.join((o, 'dir'))
            if dirkey in config['paths']:
                dirvalue = config['paths'][dirkey]
            else:
                dirvalue = ''
            value = os.path.join(dirvalue, value)
            for k, v in myrepl.iteritems():
                if k in value:
                    value = value.replace(k, v)
            for dk, dv in defrepl.iteritems():
                if dk in value:
                    value = value.replace(dk, dv)
            field_template.update({o: value})
            
        return field_template
        

class FileOut(DINGOFlow):
    """
    Parameters
    ----------
    name            :    Workflow name
    inputs          :    Dict
        substitutions    :  List of pairs for filename substitutions
            (s2r substitute will be replaced with subid_scanid_uid)
            e.g. [('input_id', 'id'),('dtifit_', 'input_id')] ->
                [('input_id', 'id'),('dtifit_', 'subid_scanid_uid')]
        s2r             :   Str
            replace in substitutions
        infields        :   List of output fields
        iterfield       :   Str, infield used as iterfield, will make sink a mapnode
        parent_dir      :   Str
        sub_id          :   Str
        scan_id         :   Str
        uid             :   Str
        container       :   Str, default '{0}/{1}'
        container_args  :   List, default ['sub_id', 'scan_id']
        
    Returns
    -------
    fileout Nipype workflow
    
    Outputs
    -------
    Files written with defaults to parent_dir/sub_id/scan_id/
    """
    inputnode = 'inputnode'
    outputnode = 'sink'
    
    connection_spec = {
        'sub_id':   ['SplitIDs', 'sub_id'],
        'scan_id':  ['SplitIDs', 'scan_id'],
        'uid':      ['SplitIDs', 'uid']
    }
    
    def __init__(self,
                 name='FileOut_SubScanUID',
                 inputs=dict(
                     substitutions=None,
                     s2r=None,
                     regexp_substitutions=None,
                     iterfield=None, infields=None,
                     parent_dir=None,
                     sub_id=None, scan_id=None, uid=None,
                     container=None, container_args=None),
                 **kwargs):

        super(FileOut, self).__init__(name=name, **kwargs)
            
        inputfields = ['parent_dir', 'sub_id', 'scan_id', 'uid']
        if 'infields' in inputs and inputs['infields'] is not None:
            infields = inputs['infields']
        else:
            infields = []
        inputfields.extend((field.replace('.', '_') for field in infields))
        inputnode = pe.Node(
            name='inputnode',
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
        if 'container' in inputs and inputs['container'] is not None:
            inputnode.inputs.container = inputs['container']
        else:
            inputnode.inputs.container = '{0}/{1}'
        if 'container_args' in inputs and inputs['container_args'] is not None:
            inputnode.inputs.container_args = inputs['container_args']
        else:
            inputnode.inputs.container_args = ['sub_id', 'scan_id']
                
        # Could possibly replace with function in connect statement
        prefix = pe.Node(
            name='prefix',
            interface=Function(
                input_names=['sep', 'arg0', 'arg1', 'arg2'],
                output_names=['pref_string'],
                function=join_strs))
        prefix.inputs.sep = '_'
        
        subs = pe.Node(
            name='substitutions',
            interface=Function(
                input_names=['subs', 's2r', 'rep'],
                output_names=['new_subs'],
                function=self.substitutions))
                
        sinkargs = {}
        if 'iterfield' in inputs and inputs['iterfield'] is not None:
            nodetype = pe.MapNode
            sinkargs.update(dict(iterfield=inputs['iterfield']))
        else:
            nodetype = TRKnode
        
        sink = nodetype(
            name='sink',
            interface=nio.DataSink(infields=infields,
                                   parameterization=False),
            **sinkargs)
        
        if 's2r' in inputs and inputs['s2r'] is not None:
            subs.inputs.s2r = inputs['s2r']
            if ('substitutions' in inputs and
                    inputs['substitutions'] is not None):
                subs.inputs.subs = inputs['substitutions']
        elif 'substitutions' in inputs and inputs['substitutions'] is not None:
            sink.inputs.substitutions = tuple(inputs['substitutions'])
            
        if ('regexp_substitutions' in inputs and
                inputs['regexp_substitutions'] is not None):
            sink.inputs.regexp_substitutions = tuple(
                inputs['regexp_substitutions'])
        
        for field in infields:
            self.connect([
                (inputnode, sink, 
                    [(field.replace('.', '_'), field)])
            ])
           
        cont = pe.Node(
            name='container',
            interface=Function(
                input_names=['sub_id', 'scan_id', 'uid', 
                             'container', 'container_args'],
                output_names=['cont_string'],
                function=self.container))
        
        # finally
        self.connect([
            (inputnode, prefix, 
                [('sub_id', 'arg0'),
                 ('scan_id', 'arg1'),
                 ('uid', 'arg2')]),
            (inputnode, cont,
                [('sub_id', 'sub_id'),
                 ('scan_id', 'scan_id'),
                 ('uid', 'uid'),
                 ('container', 'container'),
                 ('container_args', 'container_args')]),
            (inputnode, sink,
                [('parent_dir', 'base_directory')]),
            (cont, sink,
                [('cont_string', 'container')]),
            (prefix, subs,
                [('pref_string', 'rep')]),
            (subs, sink,
                [('new_subs', 'substitutions')])
        ])
                    
    def container(sub_id=None, scan_id=None, uid=None,
                  container=None, container_args=None):
        from traits.trait_base import _Undefined
        import os.path as op
        if container_args is None:
            container_args = tuple()
        strings = [locals()[k] for k in container_args]
        if container is not None:
            return op.join(container.format(*strings))
        else:
            return _Undefined()

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
