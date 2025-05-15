# Visualize Kubernetes cluster resources with MERMAID


> Please refer to the attached doc "Visualize kubernetes resources with Mermaid.docx" to know better insights about this project

## How to un the python file ? ##

kubectl get all,pvc -n default -o yaml > FILE_NAME.yaml

Python3 mermaid-k8s-all.py NAME_OF_THE_YAML_FILE_INPUT_FROM_USER_CLUSTER
Example :   Python3 mermaid-k8s-all.py  FILE_NAME.yaml


Once the python file runs successfully, It will generate an output .MMD file: Mermaid_class_diagram_output.mmd

Open any EDITOR where Mermaid Plugin is installed. you can see the MMD file in class diagram format
