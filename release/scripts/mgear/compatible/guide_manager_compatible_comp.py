import os
import sys
import traceback
import importlib

import maya.cmds as cmds
import mgear.pymaya as pm
from mgear import shifter
from mgear.shifter import guide_template
from mgear.compatible import compatible_comp as rc

importlib.reload(rc)

PY2 = sys.version_info[0] == 2


def get_component_list():
    """
    Retrieves a list of all available mGear component types.
    Scans both default and custom component directories.

    """
    comp_list = []
    compDir = shifter.getComponentDirectories()
    trackLoadComponent = []

    for path, comps in compDir.items():
        for comp_name in comps:
            if comp_name == "__init__.py" or comp_name == "__pycache__":
                continue
            if comp_name in trackLoadComponent:
                pm.displayWarning(
                    "Custom component name: %s conflicts with default component. "
                    "Skipping load." % comp_name
                )
                continue
            else:
                trackLoadComponent.append(comp_name)
            if not os.path.exists(os.path.join(path, comp_name, "__init__.py")):
                continue
            try:
                module = shifter.importComponentGuide(comp_name)
                if PY2:
                    reload(module)
                else:
                    importlib.reload(module)
                comp_list.append(module.TYPE)
            except Exception as e:
                pm.displayWarning("加载组件失败：{}".format(comp_name))
                pm.displayError(str(e))
                pm.displayError(traceback.format_exc())

    return comp_list


def get_comp_root():
    """
    Finds the root component node for selected objects.
    Traverses up the hierarchy to find nodes with 'comp_type' or 'ismodel' attributes.

    """
    oSel = pm.selected()
    if not oSel:
        pm.displayWarning("请从组件指南中至少选择一个对象")
        return []

    roots = []
    for obj in oSel:
        current = obj
        root = None
        while current:
            if pm.attributeQuery("comp_type", node=current, ex=True):
                root = current
                break
            elif pm.attributeQuery("ismodel", node=current, ex=True):
                root = current
                break
            current = current.getParent()
        roots.append(root)

    return roots


def are_comp_names_identical(roots):
    """
    Checks if all selected components have the same base type.
    Handles special case for EPIC components.

    """
    base_value = None
    for obj in roots:
        if not obj:
            continue
        if not cmds.attributeQuery("comp_type", exists=True, node=obj):
            cmds.warning(f"Object {obj} is missing comp_type attribute")
            return False

        root_comp_type = obj.getAttr("comp_type")
        type_parts = root_comp_type.split("_")
        base_type = type_parts[0]
        sub_type = type_parts[1] if len(type_parts) > 1 else ""

        if base_type == "EPIC":
            current_value = f"{base_type}_{sub_type}"
        else:
            current_value = base_type
        if base_value is None:
            base_value = current_value
            continue
        if current_value != base_value:
            return False

    return True


def set_selected_component_type_is_manager_current_selected_Component(roots, comp):
    """
    Sets the comp_type attribute for selected component roots.

    """
    if roots:
        for node in roots:
            if node and node.hasAttr("comp_type"):
                node.comp_type.set(comp)
            else:
                pm.displayWarning("选中的对象不是有效的mGear组件根")
    else:
        pm.displayWarning("请至少选择一个mGear组件")


def update_component_type_and_update_guide(component, update_guide=False):
    """
    Updates component type and optionally refreshes the guide.

    Args:
        component: Component type to set
        update_guide (bool): Whether to update the guide after change
    """
    root_components = get_comp_root()
    if not root_components:
        pm.displayWarning("未选择有效的组件")
        return
    if not are_comp_names_identical(root_components):
        pm.displayWarning("选中的组件类型不一致")
        return
    set_selected_component_type_is_manager_current_selected_Component(
        root_components, component
    )
    if update_guide:
        pm.select(root_components)
        guide_template.updateGuide()
        pm.select(clear=True)
