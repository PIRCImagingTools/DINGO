# DINGO
Semi-Automated Neonatal Tractography Pipeline

## Overview
This is an extension of nipype used to conduct analysis of diffusion MRI data in a semi-automated fashion using FSL and DSI Studio. It allows you to specify the analysis steps in a json file to quickly set up and potentially iteratively improve the inputs to the workflow.

## Install
### Requirements
 - [Docker](https://www.docker.com/)
 - [Nipype](http://nipy.org/packages/nipype/index.html)
 - [FSL](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/)
 - [DSI Studio](http://dsi-studio.labsolver.org/)

### Docker Install
1) [Download](https://pitt.box.com/s/3tbmknwhbj8x55dv4yq7nwexy560iqg3) the image.
2) docker load -i /path/to/dingo_dsi-feb2019.tar
3) On Linux for convenient use add the following to ~/.bashrc
   - function DINGO { docker run -it --rm --user=$UID:$UID -v /tmp/.X11-unix:/tmp/.X11-unix:ro -e DISPLAY=$DISPLAY -v $(pwd):/data dingo:dsi-feb2019 "$@"; }

### Non-Docker Install
1) Install Nipype, FSL, DSI Studio.
2) [Download](https://github.com/PIRCImagingTools/DINGO/archive/master.zip) and extract the repository.
3) Add the DINGO directory to your python path (by adding /path/to/DINGO to your PYTHONPATH environment variable or a new line in a .pth file in your site-packages directory)

## Config Setup
An analysis config specifies the workflow to be created. Several examples can be found in [res](https://github.com/PIRCImagingTools/DINGO/tree/master/res).

### Required Keys
  - name          : String, new nipype workflow directory that will be created in the current working directory.
  - data_dir      : String, parent directory to each patient's folder, will be prepended to FileIn, FileOut.
  - included_ids  : List, strings specifying included data "patientID_scanID_uniqueSUFFIX"
  - steps         : List, analysis steps to perform, ["Step1", ["NameofStep2","Step2"], ["NameofStep3","Step2"] ]
  
### Optional Keys
  - method        : Dictionary, if key does not exist for each step, will use default parameters for it.
      - \<Name\>    : Dictionary
        - inputs  : Dictionary, { parameter : value }, ( used parameters found in nipype InputSpec )
        - connect : Dictionary, { parameter : [ "SourceStepName", "SourceStepParameter" ] }
  - email         : Dictionary, email will be sent by smtp at the conclusion of the workflow
      - server    : String, "smtp.server:port"
      - login     : String, username
      - pw        : String, password
      - fromaddr  : String
      - toaddr    : String


## Usage
### Docker Usage
```
DINGO run /data/path/to/config.json
```

### Non-Docker Usage
```
python
from DINGO.base import DINGO
aworkflow = DINGO('/path/to/config.json')
aworkflow.run()
```
OR
```
python /path/to/DINGO/DINGO/base.py /path/to/config.json
```
