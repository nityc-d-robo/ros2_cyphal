#!/usr/bin/env python3
import argparse
import xml.etree.ElementTree as ET
from jinja2 import Environment, FileSystemLoader

def dsdl_to_c_info(dsdl_string):
    parts = dsdl_string.split('.')
    name_parts = parts[:-2]
    version = f"{parts[-2]}_{parts[-1]}"
    c_type = "_".join(name_parts) + "_" + version
    c_header = "/".join(name_parts) + "_" + version + ".h"
    return c_type, c_header

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bus", required=True, help="Path to bus.xml (cyphal mapping config)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--template-dir", required=True)
    args = parser.parse_args()

    root = ET.parse(args.bus).getroot()

    rx_joints = []
    tx_joints = []
    headers = set()

    for i, joint in enumerate(root.findall("joint")):
        for state_node in joint.findall("state"):
            dsdl_type = state_node.get("dsdl_type")
            subject_id = state_node.get("subject_id")
            c_type, c_header = dsdl_to_c_info(dsdl_type)
            headers.add(c_header)

            mappings = [
                {"interface": m.get("interface"), "member": m.get("member")}
                for m in state_node.findall("map")
            ]

            rx_joints.append({
                "index": i,
                "subject_id": subject_id,
                "c_type": c_type,
                "mappings": mappings
            })

        for command_node in joint.findall("command"):
            dsdl_type = command_node.get("dsdl_type")
            subject_id = command_node.get("subject_id")
            c_type, c_header = dsdl_to_c_info(dsdl_type)
            headers.add(c_header)

            mappings = [
                {"interface": m.get("interface"), "member": m.get("member")}
                for m in command_node.findall("map")
            ]

            tx_joints.append({
                "index": i,
                "subject_id": subject_id,
                "c_type": c_type,
                "mappings": mappings
            })

    env = Environment(loader=FileSystemLoader(args.template_dir))
    template = env.get_template("joint_router.hpp.jinja2")
    with open(args.output, "w") as f:
        f.write(template.render(
            headers=sorted(list(headers)),
            rx_joints=rx_joints,
            tx_joints=tx_joints,
        ))

if __name__ == "__main__":
    main()
