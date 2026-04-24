import re
import importlib

import maya.cmds as cmds
import mgear.pymaya as pm
from mgear.shifter import guide_template
from mgear.compatible import compatible_comp as rc
from mgear.compatible import (
    guide_manager_compatible_comp as gmcr,
)

importlib.reload(rc)
importlib.reload(gmcr)

SPECIAL_TYPES = ["EPIC", "lite"]


def update_component_type_and_update_guide_with_dagmenu(*args):
    """
    Updates the component type of selected guide components and optionally refreshes the guide.
    Provides a user interface for selecting related component types and filtering methods.

    Features:
    - Validates selected components and their types
    - Provides filtering options for related components
    - Updates component types while maintaining guide structure
    - Optionally refreshes the guide template after update

    """
    roots = gmcr.get_comp_root()

    if not roots:
        pm.displayWarning("未选择任何组件。")
        return

    if not gmcr.are_comp_names_identical(roots):
        pm.displayWarning("选中的组件类型不一致。")
        return

    root_comp_type = roots[0].getAttr("comp_type")
    if not isinstance(root_comp_type, str):
        cmds.error(
            f"Expected string type for comp_type, but got {type(root_comp_type).__name__}"
        )
    elif not root_comp_type:
        cmds.error("comp_type is empty or invalid")
    if not re.fullmatch(r"^[a-zA-Z]+(?:_[a-zA-Z0-9_-]+)?$", root_comp_type):
        cmds.error(
            f"Invalid format: '{root_comp_type}'\n"
            "Correct format should be: BASE_TYPE or BASE_TYPE_SUB_TYPE\n"
            "Examples: EPIC_spine or arm_2jnt"
        )

    type_parts = root_comp_type.split("_")
    base_type = type_parts[0]
    sub_type = type_parts[1] if len(type_parts) > 1 else ""
    all_components = gmcr.get_component_list()

    buttons = []
    if base_type in SPECIAL_TYPES:
        buttons = [
            f"Only match '{base_type}' type",
            f"Match all containing '{sub_type}' type",
            "取消",
        ]
    else:
        buttons = [
            f"Only match '{base_type}' type",
            f"匹配所有包含 '{base_type}' 类型",
            "取消",
        ]

    choice = pm.confirmDialog(
        title="选择相关组件范围",
        message="请选择要包含的相关组件范围",
        button=buttons,
        defaultButton=f"匹配所有包含 '{base_type}' 类型",
        cancelButton="取消",
        dismissString="取消",
    )
    if choice == "取消":
        return

    related_components = []
    for component in all_components:
        comp_parts = component.split("_")
        if choice == f"Only match '{base_type}' type":
            if base_type in SPECIAL_TYPES:
                if (
                    len(comp_parts) > 1
                    and comp_parts[0] == base_type
                    and comp_parts[1] == sub_type
                ):
                    related_components.append(component)
            else:
                if comp_parts[0] == base_type:
                    related_components.append(component)
        else:
            if base_type in SPECIAL_TYPES:
                if len(comp_parts) > 1 and comp_parts[1] == sub_type:
                    related_components.append(component)
                elif sub_type and sub_type in component:
                    related_components.append(component)
            else:
                if base_type in component:
                    related_components.append(component)

    if not related_components:
        pm.displayWarning(f"未找到与 '{root_comp_type}' 相关的组件。")
        return

    custom_window = rc.exec_window(related_components)
    if not custom_window or not custom_window.result_components:
        return

    gmcr.set_selected_component_type_is_manager_current_selected_Component(
        roots, custom_window.result_components
    )

    if custom_window.update_flag:
        pm.select(roots)
        guide_template.updateGuide()
        pm.select(clear=True)
