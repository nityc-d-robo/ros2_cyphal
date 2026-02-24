#!/usr/bin/env python3
import argparse
import xml.etree.ElementTree as ET
import subprocess
from jinja2 import Environment, FileSystemLoader

def dsdl_to_c_info(dsdl_string):
    # "reg.udral...Planar.0.1" -> "reg_udral_..._0_1", "reg/udral/.../Planar_0_1.h"
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

    # ルートが <ros2_control> 直接（xacroスニペット）の場合と
    # <robot> ルートのフルURDFの場合の両方に対応
    if root.tag == "ros2_control":
        joint_elements = root.findall("joint")
    else:
        joint_elements = root.findall(".//ros2_control/joint")

    for i, joint in enumerate(joint_elements):
        params = {p.get("name"): p.text for p in joint.findall("param")}

        # --- RX ---
        if "rx_dsdl_type" in params and "rx_subject_id" in params:
            c_type, c_header = dsdl_to_c_info(params["rx_dsdl_type"])
            headers.add(c_header)

            mappings = []
            for key, value in params.items():
                if key.startswith("map_state_"):
                    mappings.append({
                        "interface": key.replace("map_state_", ""),
                        "member": value
                    })

            rx_joints.append({
                "index": i,
                "subject_id": params["rx_subject_id"],
                "c_type": c_type,
                "mappings": mappings
            })

        # --- TX ---
        if "tx_dsdl_type" in params and "tx_subject_id" in params:
            c_type, c_header = dsdl_to_c_info(params["tx_dsdl_type"])
            headers.add(c_header)

            mappings = []
            for key, value in params.items():
                if key.startswith("map_command_"):
                    mappings.append({
                        "interface": key.replace("map_command_", ""),
                        "member": value
                    })

            tx_joints.append({
                "index": i,
                "subject_id": params["tx_subject_id"],
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
