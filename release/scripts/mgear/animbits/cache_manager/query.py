
# imports
from __future__ import absolute_import
from datetime import datetime
import os
import json
from maya import cmds

# =============================================================================
# 常量
# =============================================================================

_MANAGER_CACHE_DESTINATION = os.getenv("MGEAR_CACHE_MANAGER_CACHE_DESTINATION")
_MANAGER_MODEL_GROUP = os.getenv("MGEAR_CACHE_MANAGER_MODEL_GROUP")
_MANAGER_PREFERENCE_FILE = "animbits_cache_manager.json"
_MANAGER_PREFERENCE_PATH = "{}/mGear".format(os.getenv("MAYA_APP_DIR"))
_MANAGER_RIG_ATTRIBUTE = os.getenv("MGEAR_CACHE_MANAGER_RIG_ATTRIBUTE")
# ==============================================================================


def find_model_group_inside_rig(geo_node, rig_node):
    """在装配体的层级结构中查找给定的组名

    Args:
        geo_node (str): 包含要缓存形状的几何组变换节点
        rig_node (str): 包含 geo_node 的装配体根节点

    Returns:
        str 或 None: 找到时返回 geo_node 的完整路径，否则返回 None
    """

    try:
        model_group = None
        for x in cmds.ls(cmds.listRelatives(rig_node, allDescendents=True,
                                            fullPath=True), type="transform"):
            if x.split("|")[-1].split(":")[-1] == geo_node:
                model_group = x
                break

        if not model_group:
            for x in cmds.ls(cmds.listRelatives(cmds.listRelatives(
                             rig_node, parent=True)[0], allDescendents=True,
                             fullPath=True), type="transform"):
                if x.split("|")[-1].split(":")[-1] == geo_node:
                    model_group = x
                    break

        if model_group:
            return model_group
        else:
            print("无法在装配体节点中找到几何节点。")

    except Exception as e:
        if cmds.objExists("{}_cache".format(rig_node)):
            return
        print("无法在装配体节点中找到几何节点。"
              "请联系mGear开发者报告此问题以获得帮助")
        raise e


def get_cache_destination_path():
    """返回缓存目标路径

    此方法返回缓存管理器将存储 GPU 缓存的路径。

    如果设置了 **MGEAR_CACHE_MANAGER_CACHE_DESTINATION** 环境变量，
    它将返回该有效路径。

    如果未设置或无法使用该路径，此方法将尝试返回
    **缓存管理器首选项文件** 中设置的路径。

    最后，如果未设置环境变量或首选项文件，则使用 **系统临时文件夹** 作为目标路径。

    Returns:
        str: 缓存目标路径
    """

    # if env variable is set
    if (_MANAGER_CACHE_DESTINATION and
            os.path.exists(_MANAGER_CACHE_DESTINATION)):
        return _MANAGER_CACHE_DESTINATION

    # if pref file exists
    cache_path = get_preference_file_cache_destination_path()
    if cache_path:
        return cache_path

    # returns temp. folder
    return os.getenv("TMPDIR")


def get_time_stamp():
    """以文件名友好的方式返回日期和时间

    这用于创建缓存文件名，使其具有唯一名称，以避免
    不同特定场景使用的缓存文件发生冲突覆盖。

    Returns:
        str: 时间戳 (19-05-12_14-10-55) 年-月-日_时-分-秒
    """

    return datetime.now().strftime('%y-%m-%d_%H-%M-%S')


def get_model_group(ignore_selection=False):
    """返回要缓存的模型组名称

    此方法返回缓存几何体/模型时使用的变换节点名称。

    如果设置了 **MGEAR_CACHE_MANAGER_MODEL_GROUP** 环境变量，
    将返回其中存储的名称。

    如果未设置或无法使用该名称，此方法将尝试返回
    **缓存管理器首选项文件** 中设置的名称。

    最后，如果未设置环境变量或首选项文件，则回退到选择。

    此方法不检查返回值是否有效（例如变换节点是否存在），
    因为此阶段不知道资产是否在命名空间内或有场景特定设置。
    这是通用检查，只检查通用部分。

    Args:
        ignore_selection (bool): 是否回退到选择的组

    Returns:
        str 或 None: 组名或 None
    """

    # if env variable is set
    if _MANAGER_MODEL_GROUP:
        return _MANAGER_MODEL_GROUP

    # if pref file exists
    model_group = get_preference_file_model_group()
    if model_group:
        return model_group

    # returns selection
    selection = cmds.ls(selection=True)
    if selection and not ignore_selection:
        return selection[0]


def get_preference_file():
    """返回首选项文件路径和名称

    Returns:
        str: 首选项文件路径和名称
    """

    return "{}/{}".format(_MANAGER_PREFERENCE_PATH, _MANAGER_PREFERENCE_FILE)


def get_preference_file_cache_destination_path():
    """返回首选项文件中设置的文件夹路径

    Returns:
        str 或 None: 首选项文件中存储的路径，无效时返回 None
    """

    return read_preference_key(search_key="cache_manager_cache_path")


def get_preference_file_model_group():
    """返回首选项文件中设置的模型组名称

    Returns:
        str 或 None: 首选项文件中存储的模型组名称，无效时返回 None
    """

    return read_preference_key(search_key="cache_manager_model_group")


def get_scene_rigs():
    """当前 Maya 会话中的装配体

    此方法在当前 Maya 场景中搜索装配体。
    如果设置了 MGEAR_CACHE_MANAGER_RIG_ATTRIBUTE，将尝试根据
    环境变量设置的属性查找装配体。否则将使用
    **gear_version** 属性来查找场景中的装配体。

    Returns:
        list 或 None: mGear 装配体顶层节点或 None
    """

    if _MANAGER_RIG_ATTRIBUTE:
        try:
            rigs = [x.split(".")[0] for x in cmds.ls(
                "*.{}".format(_MANAGER_RIG_ATTRIBUTE), recursive=True)]
        except RuntimeError:
            raise ValueError("Invalid attribute key: {} - is not a valid "
                             "attribute key to set on the "
                             "MGEAR_CACHE_MANAGER_RIG_ATTRIBUTE variable"
                             .format(_MANAGER_RIG_ATTRIBUTE))
    else:
        rigs = [x.split(".")[0] for x in cmds.ls("*.is_rig", recursive=True)]

    # we query the gpu caches node rig_link custom attribute in the scene
    # in order to keep the returned value accurate.
    # If we have a scene in which a rig has already been cached and the
    # reference unloaded we can't find the rig node anymore on the scene so
    # we use the custom attribute added by the load_gpu_cache method to query
    # caches been created by the cache manager.
    [rigs.append(cmds.getAttr("{}.rig_link".format(x)))
     for x in cmds.ls(type="gpuCache")
     if cmds.objExists("{}.rig_link".format(x))
     and cmds.getAttr("{}.rig_link".format(x)) not in rigs]

    return rigs or None


def get_timeline_values():
    """返回当前播放范围的最小和最大关键帧值

    为了给艺术家更多自由度，我们始终评估播放范围
    而不是动画范围，以便艺术家可以选择创建 GPU 缓存时
    使用的范围。

    Returns:
        float, float: 最小值和最大值
    """

    # get user timeline playback frame range
    _min = cmds.playbackOptions(query=True, minTime=True)
    _max = cmds.playbackOptions(query=True, maxTime=True)

    return _min, _max


def is_rig(rig_node):
    """返回给定的装配体节点是否处于装配状态或缓存状态

    Args:
        rig_node (str): 装配体节点名称
    """

    if not cmds.objExists(rig_node) or (
            cmds.objExists("{}_cache".format(rig_node))):
        return False

    return True


def read_preference_key(search_key):
    """返回首选项文件中给定键存储的首选项

    Returns:
        str 或 None: 首选项文件中存储的路径，无效时返回 None
    """

    # preference file
    pref_file = get_preference_file()

    try:
        with open(pref_file, 'r') as file_r:
            # reads json file and get the preference
            json_dict = json.load(file_r)
            value = json_dict[search_key]

            if type(value) == int:
                return value

            if len(value) and type(value) != int:
                return value

            print("首选项文件中保存的键 -{}- 对于 {} 无效"
                  .format(value, search_key))

    except Exception as e:
        message = "请联系mGear开发者报告此问题以获得帮助"
        print("{} - {} / {}".format(type(e).__name__, e,
                                    message))
        return
