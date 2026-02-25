#!/usr/bin/env python3
import argparse
import xml.etree.ElementTree as ET
import subprocess
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
    parser.add_argument("--xacro", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--template-dir", required=True)
    args = parser.parse_args()

    # Xacro展開
    urdf_xml = subprocess.check_output(["xacro", args.xacro]).decode('utf-8')
    root = ET.fromstring(urdf_xml)

    rx_joints = []
    tx_joints = []
    headers = set()

    joint_elements = root.findall(".//ros2_control/joint")

    for i, joint in enumerate(joint_elements):
        # <cyphal> タグを探す
        cyphal_node = joint.find("cyphal")
        if cyphal_node is None:
            continue # cyphal設定がないジョイントはスキップ

        # --- State (デバイスから状態を受信) ---
        for state_node in cyphal_node.findall("state"):
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

        # --- Command (デバイスへ指令を送信) ---
        for command_node in cyphal_node.findall("command"):
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
