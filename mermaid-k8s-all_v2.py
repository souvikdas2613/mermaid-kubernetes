import yaml
import sys

### Function to get Genral RESOURCE Dictionary
def get_common_resource_and_key_from_object(doc):
    kind = doc['kind']
    metadata = doc.get('metadata', {})
    spec = doc.get('spec', {})
    name = metadata.get('name', 'Unnamed')
    namespace = metadata.get('namespace', 'default')
    labels = metadata.get('labels', {})
    api_version = doc.get('apiVersion', 'Unknown')

    resource = {
        'kind': kind,
        'api_version': api_version,
        'name': name,
        'namespace': namespace,
        'service_account_name': None,
        'image': None,
        'ports': [],
        'labels': labels,
        'pod_replicas': 0,
    }
    key = f"{kind}_{namespace}_{name}"
    return key, resource, metadata, spec

## get_relationship_deploy_sts_ds_job gets called from parse_kubernetes_resources function
def get_relationship_deploy_sts_ds_job(resource, relationships, metadata, spec):
    print ("am here 1   :  " +str(resource['kind']))
    resource['pod_replicas'] = spec.get('replicas',0)
    pod_spec = spec.get('template', {}).get('spec', {})
    resource['service_account_name'] = pod_spec.get('serviceAccountName')
    resource['labels'] = spec.get('template', {}).get('metadata', {}).get('labels',{})
    containers = pod_spec.get('containers', [])
    if containers:
        for c in containers:
            resource['image'] = c.get('image')
            for env in c.get('env', []):
                value_from = env.get('valueFrom', {})
                for ref_type in ['secretKeyRef', 'configMapKeyRef']:
                    ref = value_from.get(ref_type)
                    if ref:
                        relationships.append({
							'source_kind': resource['kind'],
							'source_name': resource['name'],
							'relation': f"uses_{ref_type.replace('KeyRef', '').lower()}",
							'target_kind': ref_type.replace('KeyRef', '').replace('Ref', ''),
							'target_name': ref['name'],
							'namespace': resource['namespace'],
							'pod_selectors': resource['labels'],
							'pod_relation': 'Create_pods',
						})
            for env_from in c.get('envFrom', []):
                for ref_type in ['secretRef', 'configMapRef']:
                    ref = env_from.get(ref_type)
                    if ref:
                        relationships.append({
							'source_kind': resource['kind'],
							'source_name': resource['name'],
							'relation': f"uses_{ref_type.replace('Ref', '').lower()}",
							'target_kind': ref_type.replace('Ref', ''),
							'target_name': ref['name'],
							'namespace': resource['namespace'],
							'pod_selectors': resource['labels'],
							'pod_relation': 'Create_pods',
						})
    if resource['kind'] !="StatefulSet":
        vol_flag = False
        print (vol_flag)
        print ("not a statefullset   :  "  +str(resource['name']))
        volumes = pod_spec.get('volumes', [])
        if not volumes:
			### NO VOLUMES in Resource..
            relationships.append({
				'source_kind': resource['kind'],
				'source_name': resource['name'],
				'namespace': resource['namespace'],
				'pod_selectors': resource['labels'],
				'pod_relation': 'Create_pods',
			})
        else:
            vol_flag = False
            for volume in pod_spec.get('volumes', []):
                for vol_type in ['configMap', 'secret', 'persistentVolumeClaim']:
                    vol = volume.get(vol_type)
                    if vol:
                        vol_flag = True
                        print ("am here .... 10")
                        relationships.append({
							'source_kind': resource['kind'],
							'source_name': resource['name'],
							'relation': f"mounts_{vol_type.lower()}",
							'target_kind': vol_type.capitalize(),
							'target_name': vol.get('name') or vol.get('claimName') or vol.get('secretName'),
							'namespace': resource['namespace'],
							'pod_selectors': resource['labels'],
							'pod_relation': 'Create_pods',
						})
			#else:
            if not vol_flag:
                print ("am here .... 11")
                relationships.append({
					'source_kind': resource['kind'],
					'source_name': resource['name'],
					'namespace': resource['namespace'],
					'pod_selectors': resource['labels'],
					'pod_relation': 'Create_pods',
				})
    else:
        sts_volume_spec = spec.get('volumeClaimTemplates', [])
        if sts_volume_spec:
            print (sts_volume_spec)
            for pvc in sts_volume_spec:
                pvc_name = pvc.get('metadata', {}).get('name','XXXXX')
                print (pvc_name)
                relationships.append({
					'source_kind': resource['kind'],
					'source_name': resource['name'],
					'relation': "mounts_persistentvolumeclaim",
					'target_kind': "Persistentvolumeclaim",
					'target_name': pvc_name,
					'namespace': resource['namespace'],
					'pod_selectors': resource['labels'],
					'pod_relation': 'Create_pods',
					'pod_replicas': resource['pod_replicas'],
				})
        else:
            relationships.append({
					'source_kind': resource['kind'],
					'source_name': resource['name'],
					'namespace': resource['namespace'],
					'pod_selectors': resource['labels'],
					'pod_relation': 'Create_pods',
				})
	
    if resource['service_account_name']:
        relationships.append({
			'source_kind': resource['kind'],
			'source_name': resource['name'],
			'relation': 'uses_serviceaccount',
			'target_kind': 'ServiceAccount',
			'target_name': resource['service_account_name'],
			'namespace': resource['namespace']
                })
    return relationships

## get_relationship_service gets called from parse_kubernetes_resources function    
def get_relationship_service(resource,relationships, metadata, spec):
    resource['ports'] = [(p.get('port'),p.get('nodePort'), p.get('targetPort') ,p.get('protocol', 'TCP')) for p in spec.get('ports', [])]
    selector = spec.get('selector', {})
    if selector:
        relationships.append({
            'source_kind': 'Service',
            'source_name': resource['name'],
            'relation': 'targets',
            'target_selector': selector,
            'namespace': resource['namespace']
        })
    return relationships

## get_relationship_ingress gets called from parse_kubernetes_resources function  
def get_relationship_ingress (resource,relationships, metadata, spec):
    for rule in spec.get('rules', []):
        for path in rule.get('http', {}).get('paths', []):
            service = path.get('backend', {}).get('service', {})
            if service:
                relationships.append({
                    'source_kind': 'Ingress',
                    'source_name': resource['name'],
                    'relation': 'routes_to',
                    'target_kind': 'Service',
                    'target_name': service.get('name'),
                    'namespace': resource['namespace'],
                })
    return relationships

## get_relationship_networkpolicy gets called from parse_kubernetes_resources function
def get_relationship_networkpolicy(resource,relationships, metadata, spec):
    relationships.append({
        'source_kind': 'NetworkPolicy',
        'source_name': resource['name'],
        'relation': 'applies_to',
        'target_selector': spec.get('podSelector', {}).get('matchLabels', {}),
        'namespace': resource['namespace']
    })
    return relationships

## get_relationship_hpa gets called from parse_kubernetes_resources function
def get_relationship_hpa(resource,relationships, metadata, spec):
    scale_target = spec.get('scaleTargetRef', {})
    relationships.append({
        'source_kind': 'HorizontalPodAutoscaler',
        'source_name': resource['name'],
        'relation': 'controls',
        'target_kind': scale_target.get('kind'),
        'target_name': scale_target.get('name'),
        'namespace': resource['namespace']
    })
    return relationships

## get_relationship_pod gets called from parse_kubernetes_resources function
def get_relationship_pod(resource,relationships, metadata, spec):
    print ("am here in pod ..."  +resource['name'])
    vol_spec = spec.get('volumes', [])
    for i in vol_spec:
        print (type(i))
        for vol_type in ['configMap', 'secret', 'persistentVolumeClaim']:
                vol = i.get(vol_type)
                if vol:
                    relationships.append({
                        'source_kind': 'Pod',
                        'source_name': resource['name'],
                        'namespace': resource['namespace'],
                        'labels': resource['labels'],
                        'relation': f"mounts_{vol_type.lower()}",
                        'target_kind': vol_type.capitalize(),
                        'target_name': vol.get('name') or vol.get('claimName') or vol.get('secretName'),
                    })
    return relationships

## get_class_diagram_alone function gets called from generate_mermaid_classdiagram_from_yaml
def get_class_diagram_alone(mermaid_output,entity_mapping,resources):
    for key, res in resources.items():
        entity_name = entity_mapping[key.upper()]
        if "ReplicaSet" not in entity_name:
            attributes = [f"+{k}: {v}" for k, v in res.items() if v and k not in ['labels','annotations']]
            mermaid_output += f"class {entity_name} {{\n  " + "\n  ".join(attributes) + "\n}\n"

    return mermaid_output

## get_relationship_diagram_for_resource_with_Volumes function gets called from generate_mermaid_classdiagram_from_yaml 
def get_relationship_diagram_for_resource_with_Volumes(mermaid_output,entity_mapping,resources, rel,source_entity):
    print ("am here 1 relationships")

    if rel['source_kind'] == 'StatefulSet':
        if 'pod_replicas' in rel:
            replicas = rel['pod_replicas']
            if replicas:
                for i in range(0, replicas):
                    target_key = f"{rel['target_kind']}_{rel['namespace']}_{rel['target_name']}-{rel['source_name']}"
                    target_key+="-"+str(i)
                    print ("target_key      :   " +str(target_key))
                    target_entity = entity_mapping.get(target_key.upper())
                    #if not target_entity:
                    #    continue
                    if target_entity:
                        mermaid_output += f"{source_entity} --> {target_entity} : {rel['relation']}\n"
    else:
        print ("am here 2 relationships not StatefulSet")
        target_key = f"{rel['target_kind']}_{rel['namespace']}_{rel['target_name']}"
        print (target_key)
        target_entity = entity_mapping.get(target_key.upper())
        print (target_entity)
        #if not target_entity:
        #    continue
        if target_entity:
            mermaid_output += f"{source_entity} --> {target_entity} : {rel['relation']}\n"
    return mermaid_output

## get_relationship_diagram_for_services function gets called from generate_mermaid_classdiagram_from_yaml
def get_relationship_diagram_for_services(mermaid_output,entity_mapping,resources, rel, source_entity):
    print ("am here 2")
    for key, res in resources.items():
        if res['namespace'] == rel['namespace'] and all(item in res['labels'].items() for item in rel['target_selector'].items()) and res['kind'] != "Pod" and res['kind'] != "ReplicaSet" and res['kind'] !="Service":
            print ("am here 3")
            target_entity = entity_mapping[key.upper()]
            mermaid_output += f"{source_entity} --> {target_entity} : {rel['relation']}\n"

    return mermaid_output

## get_relationship_diagram_for_deploy_sts_ds_creates_pods function gets called from generate_mermaid_classdiagram_from_yaml
def get_relationship_diagram_for_deploy_sts_ds_creates_pods(mermaid_output,entity_mapping, resources, rel, source_entity):
    print ("am here 4")
    print (source_entity)
    for key, res in resources.items():
        if res['namespace'] == rel['namespace'] and all(item in res['labels'].items() for item in rel['pod_selectors'].items()) and res['kind'] == "Pod" and rel['source_kind']!="Pod":
            print ("am here 5")
            target_entity = entity_mapping[key.upper()]
            print (target_entity)
            mermaid_output += f"{source_entity} --> {target_entity} : {rel['pod_relation']}\n"

    return mermaid_output

## From generate_mermaid_classdiagram_from_yaml Funtion this parse_kubernetes_resources function gets called
def parse_kubernetes_resources(yaml_file):
    resources, relationships = {}, []

    with open(yaml_file, 'r') as stream:
        try:
            data = yaml.safe_load(stream)

            # Check if it's a List of resources
            if data["kind"] == "List":
                objects = data["items"]
            else:
                # It's a single resource, not a list
                objects = [data]
            
            for doc in objects:
                if not doc or 'kind' not in doc:
                    continue
                key, resource, metadata, spec = get_common_resource_and_key_from_object(doc)

                resources[key] = resource

                ### FOR Deployment, Daemonset, Statefullset, Jobs anything which creates PODS
                if doc['kind'] in ["Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"]:
                    relationships = get_relationship_deploy_sts_ds_job(resource,relationships, metadata, spec)

                ### FOR SEVRVICE
                elif doc['kind'] == "Service":
                    relationships = get_relationship_service(resource,relationships, metadata, spec)

                ### FOR INGRESS
                elif doc['kind'] == "Ingress":
                    relationships = get_relationship_ingress(resource,relationships, metadata, spec)

                ### FOR NetworkPolicy
                elif doc['kind'] == "NetworkPolicy":
                    relationships = get_relationship_networkpolicy(resource,relationships, metadata, spec)

                ### FOR HorizontalPodAutoscaler
                elif doc['kind'] == "HorizontalPodAutoscaler":
                    relationships = get_relationship_hpa(resource,relationships, metadata, spec)

                ### FOR PODs
                elif doc['kind'] == "Pod":
                    relationships = get_relationship_pod(resource,relationships, metadata, spec)

        except yaml.YAMLError as exc:
            print(f"Error parsing {yaml_file}: {exc}")
    return resources, relationships

## from MAIN Function this Funtion :  generate_mermaid_classdiagram_from_yaml gets called
def generate_mermaid_classdiagram_from_yaml(yaml_file):
    resources, relationships = parse_kubernetes_resources(yaml_file)
    mermaid_output = "classDiagram\n"

    print ("\nresources===================================")
    print (resources)
    print ("\nrelationships===================================")
    print (relationships)
    entity_mapping ={}
    entity_mapping1 = {k: k.replace('-', '_').replace('.', '_') for k in resources}
    for key, value in entity_mapping1.items():
        entity_mapping[key.upper()]=value
    print ("entity_mapping\n===============================================\n")
    print (entity_mapping)

    mermaid_output = get_class_diagram_alone(mermaid_output,entity_mapping,resources)

    for rel in relationships:
        print ("\nRELATIONSHIP\n=======================================\n")
        print (rel)
        source_key = f"{rel['source_kind']}_{rel['namespace']}_{rel['source_name']}"
        print ("source_key :    "     +str(source_key))
        source_entity = entity_mapping.get(source_key.upper())
        print ("source_entity  :   " +str(source_entity))
        if not source_entity:
            continue

        if 'target_name' in rel and 'target_kind' in rel:
            mermaid_output = get_relationship_diagram_for_resource_with_Volumes(mermaid_output,entity_mapping,resources, rel, source_entity)
        
        if 'target_selector' in rel:
            mermaid_output = get_relationship_diagram_for_services(mermaid_output,entity_mapping, resources, rel, source_entity)

        if 'pod_selectors' in rel:
            mermaid_output = get_relationship_diagram_for_deploy_sts_ds_creates_pods(mermaid_output,entity_mapping, resources, rel, source_entity)

    return mermaid_output

#### MAIN FUNCTION ####
def main():
    n = len(sys.argv)       # total arguments = n
    #   sys.argv is Arguements array
    #   The first element, sys.argv[0], is the name of the script
    #   The following elements are the arguments provided by the user
    #   python mermaid.py a.yaml -> sys.argv[0] = name of the python script and sys.argv[1] = name of the YAML input file used to generate MERMAID file

    INPUT_YAML_FILE = sys.argv[1]
    MERMAID_CLASS_DIAGRAM_OUTPUT_FILE = 'Mermaid_class_diagram_output.mmd'

    mermaid_diagram = generate_mermaid_classdiagram_from_yaml(INPUT_YAML_FILE)
    if mermaid_diagram:
        print(mermaid_diagram)
        with open(MERMAID_CLASS_DIAGRAM_OUTPUT_FILE, 'w') as f:
            f.write(mermaid_diagram)
    else:
        print("No output generated.")

if __name__ == "__main__":
    main()