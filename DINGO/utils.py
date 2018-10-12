import os
import importlib
import copy
import json
from nipy import load_image
from nipy.core.api import Image
import numpy as np


def dice_coef(nii_A, nii_B):
    """
    Dice Coefficient:
        D = 2*(A == B)/(A)+(B)
    
    Input is two binary masks in the same 3D space
    NII format
    
    Output is a DICE score
    """
    
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
    
    return dice

def flatten(l, ltypes=(list, tuple)):
    """flatten lists and tuples to a single list, ignore empty
    
    Parameters
    ----------
    l       :    Sequence
    ltypes  :    Tuple (acceptable sequence types, default (list,tuple)
    
    Return
    ------
    l       :    Flat sequence
    
    Example
    -------
    flatten(('Hello',[' ',2],[' '],(),['the',[([' '])],('World')]))
    ('Hello', ' ', 2, ' ', 'the', ' ', 'World')
    """
    ltype = type(l)
    l = list(l)
    i = 0
    while i < len(l):
        while isinstance(l[i], ltypes):
            if not l[i]:
                l.pop(i)
                i -= 1
                break
            else:
                l[i:i+1] = l[i]
        i += 1
    return ltype(l)

def list_to_str(sep=None, args=None):
    """flattened args turned to str with separator
    default separator: ''
    
    Parameters
    ----------
    sep     :    Str (separator for join)
    args    :    List or Tuple (almost any depth, may have empties)
    
    Return
    ------
    Str (sep.join(args)
    
    Example
    -------
    list_to_str(
        sep='',args=('Hello',[' ',2],[' '],(),['the',[([' '])],('World')])
        )
    'Hello 2 the World'
    """
    if sep is None:
        sep=''
    if args is None:
        raise TypeError("Not enough arguments for str creation")
    return sep.join(str(e) for e in flatten(args))
    
def join_strs(sep=None, **kwargs):
    """Interface between list_to_str and Nipype function nodes
    
    Parameters
    ----------
    sep     :   Str (separator for join, default '')
    kwargs  :   Str (arguments will be joined by sep)
    
    Return
    ------
    Str (sep.join(kwargs.itervalues())
    
    Example
    -------
    join_strs(sep='_', arg0='foo', arg1='bar', arg2='baz')
    'foo_bar_baz'
    """
    from DINGO.utils import list_to_str
    if sep is None:
        sep=''
    arglist = []
    for arg in kwargs.itervalues():
        arglist.append(arg)
    return list_to_str(sep=sep, args=arglist)
    
def DynImport(mod=None, obj=None):
    """Import a given object from a given module
    
    Parameters
    ----------
    mod     :   Str (module name)
    obj     :   Str (object name)
    
    Return
    ------
    imported module, imported object
    
    Example
    -------
    DynImport('DINGO.utils','list_to_str') equivalent to 
    from DINGO.utils import list_to_str
    """
    import importlib
    if mod is not None:
        imp_module = importlib.import_module(mod)
        if obj is not None:
            imp_object = getattr(imp_module, obj)
            return imp_module, imp_object
        else:
            return imp_module, None
    else:
        return None, None
        
def split_filename(fname, special_extensions=None):
    """Split a filename into path, base filename, and extension.
    
    Parameters
    ----------
    fname               :    str - file or path name
    special_extensions  :    list
        list of extensions to split manually (several '.')
        
    Returns
    -------
    path    :    str - base path from fname
    fname   :    str - base filename, without extension
    ext     :    str - file extension from fname
    """
    import os
    
    default_se = ('.nii.gz', 
                '.tar.gz', 
                '.fib.gz', 
                '.src.gz',
                '.trk.gz')
    
    if special_extensions is None:
        special_extensions = default_se
    else:
        special_extensions.extend(default_se)
                            
    path = os.path.dirname(fname)
    fname = os.path.basename(fname)

    ext = None
    for special_ext in special_extensions:
        ext_len = len(special_ext)
        if (len(fname) > ext_len) and \
        (fname[-ext_len:].lower() == special_ext.lower()):
            ext = fname[-ext_len:]
            fname = fname[:-ext_len]
            break
    if not ext:
        fname, ext = os.path.splitext(fname)

    return path, fname, ext
    
def fileout_util(names=None, file_list=None, substitutions=None,\
psep='_', nsep='.', sub_id=None, scan_id=None, uid=None):
    """Utility for sinker nodes to create container, folders, substitutions
    
    Parameters
    ----------
    names           :    list - parent folder names
    file_list       :    list - files to sink
    substitutions   :    list[tuple(str, str)
        [('str2replace', 'input_id_suffix')]
    sub_id          :    str - subject id
    scan_id         :    str - scan id
    uid             :    str - unique sequence id
    psep            :    str - prefix separator for filename 
        prefix = 'sub_id{psep}scan_id{psep}uid'
    nsep            :    str - name separator for DataSink node
        'name1{nsep}name2{nsep}'
    
    
    Returns
    -------
    container       :    str - os.path.join(sub_id,scan_id)
    out_file_list   :    list[str] prefix_suffix
    newsubs         :    list[(str, str)] - [('str2replace', 'prefix_suffix')]
    """
    from DINGO.utils import list_to_str, split_filename
    import os
    #container
    container = os.path.join(sub_id, scan_id)
    
    #out_file_list
    if names is not None and isinstance(names, (list,tuple,str)):
        folder = list_to_str(sep=nsep, args=(names,''))#extra empty=add nsep
    else:
        folder = ''
    sinkfile = ''.join((folder,'@sinkfile'))
    
    setfl=[]
    if file_list is not None:
        if not isinstance(file_list, (tuple,list)):
            file_list = (file_list,)
            setfl = set().union(file_list)
            if len(setfl) != len(file_list):
                raise IndexError('file_list does not have all unique elements')
        else:
            raise TypeError('file_list is not a tuple or list')

    out_file_list = []
    for elt in setfl:
        _, newelt, _ = split_filename(elt)
        out_file_list.append(sinkfile.replace('sinkfile',newelt))
    nfiles = len(out_file_list)
    
    #newsubs
    prefix = list_to_str(sep=psep, args=(sub_id, scan_id, uid))
    newsubs = []
    if substitutions is not None and isinstance(substitutions, (list,tuple)):
        for elt in substitutions:
            newsubs.append((elt[0], elt[1].replace('input_id','prefix')))
    
    return container, out_file_list, newsubs
    
def reverse_lookup(indict, value):
    for key in indict:
        if indict[key] == value:
            return key
    raise ValueError('Value: %s, Dict: %s' % (value, indict))
    
def update_dict(indict=None, **kwargs):
    """update key/value pairs dictionary with type checking
    
    Parameters
    ----------
    indict      :    Dict
    kwargs      :    Dict / key/value pairs, key=value
    
    Returns
    -------
    outdict     :    Dict (new dictionary, indict unchanged)
    
    out=update_dict(indict=d, key=value)
    """
    import copy
    if indict is None:
        outdict = dict()
    elif not isinstance(indict, dict):
        raise TypeError('indict: %s is not a dictionary' % (indict))
    else:
        outdict = copy.deepcopy(indict)
    for k,v in kwargs.iteritems():
        if k in outdict:
            tv = type(v)
            td = type(outdict[k])
            if tv == td:
                outdict.update([(k,v)])
            else:
                raise TypeError('Type(%s): %s, != Type(%s): %s' %
                (k, tv, k, td))
        else:
            outdict.update([(k,v)])
    return outdict

#Return patient/scan id
def patient_scan(patientcfg, addSequence=None, sep=None):
    """Get patient/scan id

    Parameters
    ----------
    patientcfg      :   Dict < json (patient config file with pid, scanid in top level)
    addSequence     :   Bool (Flag to join sequence id with pid, scanid)
    sep             :   Str (separator, default '_')

    Returns
    -------
    patient_scan_id :   str (concatenated)
    """

    if "pid" in patientcfg:
        patient_id = patientcfg["pid"]
    else:
        raise KeyError("patient_config:pid")
    if "scanid" in patientcfg:
        scan_id = patientcfg["scanid"]
    else:
        raise KeyError("patient_config:scanid")
    if addSequence == None:
        addSequence = False
    if sep is None:
        sep = '_'
    ps_id = []
    ps_id.extend((patient_id,sep,scan_id))

    if addSequence: #if True, default False
        if "sequenceid" in patientcfg:
            seq_id = patientcfg["sequenceid"]
            ps_id.extend((sep,seq_id))
        else:
            raise KeyError("patient_config:sequenceid")
    patient_scan_id = "".join(ps_id)

    return patient_scan_id

#Split patient/scan id
def split_chpid(psid,sep):
    """Returns patient/scan/uid from input id
    
    Parameters
    ----------
    psid        :    Str (patient id, scan id, uid)
    sep         :    Str (separator of the ids)
    
    Returns
    -------
    patientid   :    Str (first or first two fields, depending on CHD presence)
    scanid      :    Str (second or third field)
    uid         :    Str (the rest)

    e.g. XXXX_YYYY_ZZZZ         ->  XXXX, YYYY, ZZZZ
         XXXX_YYYY_ZZZZ_ZZZZ    ->  XXXX, YYYY, ZZZZ_ZZZZ
         CHD_XXX_YYYY_ZZZZ      ->  CHD_XXX, YYYY, ZZZZ
         CHD_XXX_YYYY_ZZZZ_ZZZZ ->  CHD_XXX, YYYY, ZZZZ_ZZZZ
"""
    if not isinstance(psid, (str,unicode)):
        raise TypeError("%s is not a string" % psid)
    if not isinstance(sep, (str,unicode)):
        raise TypeError("%s is not a string" % sep)

    splitid=psid.split(sep)
    if splitid[0] == "CHD":
        subind=0
        scanind=2
        uniind=3
    else:
        subind=0
        scanind=1
        uniind=2

    subid = "_".join(splitid[subind:scanind])
    scanid = "_".join(splitid[scanind:uniind])
    uniid = "_".join(splitid[uniind:])
    return subid, scanid, uniid


#Convert to boolean
def tobool(s):
    """Convert string/int true/false values to bool
    
    Parameter
    ---------
    s        :    Boolean representation 
    
    Return
    ------
    Bool    
    
    Examples
    --------
    tobool(True)    ->    True
    tobool('t')     ->    True
    tobool('YeS')   ->    True
    tobool(1)       ->    True
    """
    true = (1, '1', 't', 'true', 'y', 'yes')
    false = (0, '0', 'f', 'false', 'n', 'no')

    if isinstance(s, bool):
        return s
    if isinstance(s, (str,unicode)):
        s = s.lower()
    if s in true:
        return True
    elif s in false:
        return False
    else:
        raise ValueError("%s cannot be converted to bool" % (s))
    
    
def add_id_subs(input_id=None, subs=None):
    """create dataout substitutions combining subs with input_id"""
    repl=[]
    if input_id is not None:
        if (subs is not None) and isinstance(subs, (list,tuple)):
            for e in subs:
                if isinstance(e, tuple) and len(e) == 2 and e[1] == 'input_id':
                    newe = (e[0],input_id)
                    repl.append(newe)
                else:
                    repl.append(e)
        else:
            msg = 'create_out_subs:repl must be list or tuple of tuples'
            raise TypeError(msg)
                    
    else:
        msg = 'create_out_subs:input_id must be specified'
        raise NameError(msg)
        
    return repl
    

def byteify(data, ignore_dicts=False):
    if isinstance(data, unicode):
        return data.encode('utf-8')
    if isinstance(data, list):
        return [byteify(item, ignore_dicts=True) for item in data]
    if isinstance(data, dict) and not ignore_dicts:
        return {
            byteify(key, ignore_dicts=True):byteify(value, ignore_dicts=True) 
            for key, value in data.iteritems()
        }
    return data
    
def json_load_byteified(handle):
    return byteify(
        json.load(handle, object_hook=byteify), ignore_dicts=True
    )
    
def read_config(configpath):
    """Read in json config file

    Parameters
    ----------
    configpath : str (absolute path to file)

    Returns
    -------
    config : dict < json
    """

    import logging
    from DINGO.utils import json_load_byteified
    logger = logging.getLogger(__name__)
    try:
        with open(configpath) as cfg_file:
            cfg = json_load_byteified(cfg_file)
            cfg_file.close()
    except Exception:
        logger.exception("Config file could not be read: " + configpath)
        raise
    return cfg
