from maya import cmds
import maya.api.OpenMaya as om2
import maya.internal.nodes.proximitywrap.node_interface as ifc

import mgear.pymaya as pm

# Backward-compat re-exports (moved to mgear.core.blendshape)
from mgear.core.blendshape import BS_TARGET_ITEM_ATTR  # noqa: F401
from mgear.core.blendshape import bs_target_weight  # noqa: F401


# =============================================================================
# DEFORMER DETECTION
# =============================================================================


def is_deformer(node):
    """检查节点是否为几何体变形器。

    使用Maya的API类层次结构(MFn.kGeometryFilt)
    检测所有变形器类型，包括自定义和
    插件变形器。

    参数:
        node (str or PyNode): 要检查的节点名称。

    返回:
        bool: 如果节点是变形器则返回True。
    """
    m_sel = om2.MSelectionList()
    try:
        m_sel.add(str(node))
    except (RuntimeError, ValueError):
        return False
    return m_sel.getDependNode(0).hasFn(om2.MFn.kGeometryFilt)


def filter_deformers(node_list):
    """过滤节点列表，仅返回变形器。

    参数:
        node_list (list): 节点名称或PyNode列表。

    返回:
        list: 仅包含变形器节点的过滤列表。
    """
    return [node for node in node_list if is_deformer(node)]


def get_deformers(mesh, deformer_type=None):
    """从网格的历史中获取变形器节点。

    参数:
        mesh (str): 网格变换名称。
        deformer_type (str, optional): 按特定Maya变形器类型名称过滤
            (例如 "skinCluster", "blendShape")。

    返回:
        list: 变形器节点名称列表。
    """
    history = (
        cmds.listHistory(mesh, pruneDagObjects=True) or []
    )
    result = [n for n in history if is_deformer(n)]
    if deformer_type:
        result = [
            n for n in result
            if cmds.nodeType(n) == deformer_type
        ]
    return result


# =============================================================================
# DEFORMER ENVELOPE MANAGEMENT
# =============================================================================


def disable_deformer_envelopes(mesh, exclude_types=None):
    """禁用网格上的所有变形器封套。

    存储原始封套值以便稍后通过
    ``restore_deformer_envelopes``恢复。对于有输入连接的封套
    使用``cmds.mute``。

    参数:
        mesh (str): 网格变换名称。
        exclude_types (set, optional): 要跳过的变形器类型名称
            (例如 ``{"blendShape"}``)。

    返回:
        dict: 变形器名称到原始状态的映射。
            值可以是浮点数(原始封套值)
            或字符串``"muted"``（如果封套被静音以禁用）。
    """
    exclude_types = exclude_types or set()
    deformers = get_deformers(mesh)
    original_envelopes = {}

    for d in deformers:
        if cmds.nodeType(d) in exclude_types:
            continue
        envelope_attr = "{}.envelope".format(d)
        try:
            original_envelopes[d] = cmds.getAttr(envelope_attr)
            cmds.setAttr(envelope_attr, 0)
        except RuntimeError:
            mute_nodes = cmds.mute(
                envelope_attr, force=True
            )
            if mute_nodes:
                cmds.setAttr(
                    "{}.hold".format(mute_nodes[0]), 0
                )
            original_envelopes[d] = "muted"

    return original_envelopes


def restore_deformer_envelopes(original_envelopes):
    """将变形器封套恢复为其原始值。

    参数:
        original_envelopes (dict): 由``disable_deformer_envelopes``返回的状态字典。
    """
    for d, val in original_envelopes.items():
        if not cmds.objExists(d):
            continue
        envelope_attr = "{}.envelope".format(d)
        if val == "muted":
            cmds.mute(
                envelope_attr, disable=True, force=True
            )
        else:
            try:
                cmds.setAttr(envelope_attr, val)
            except RuntimeError:
                pass


# =============================================================================
# WRAP DEFORMER
# =============================================================================


def create_wrap_deformer(
    target, driver, use_base_duplicate=False, name=None
):
    """在目标上创建由驱动器驱动的包裹变形器。

    支持两种基础网格策略：

    - **中间形状** (``use_base_duplicate=False``):
      连接到驱动器现有的中间(orig)形状。
      适用于驱动器在包裹生命周期内不会被修改或删除的情况。

    - **基础复制** (``use_base_duplicate=True``):
      创建一个单独的静态复制作为基础网格。
      当包裹稍后将被删除时更安全，因为它避免了损坏驱动器的变形链。

    参数:
        target (str): 要变形的目标网格变换。
        driver (str): 驱动器网格变换。
        use_base_duplicate (bool): 如果为True，创建单独的基础网格复制而不是使用驱动器的中间形状。
        name (str, optional): 包裹变形器的名称。

    返回:
        tuple: ``(wrap_node, base_dup)`` 其中base_dup是需要稍后清理的静态基础网格（仅当``use_base_duplicate=True``时），否则为None。
            失败时返回``(None, None)``。
    """
    # Get visible shape on driver
    driver_shapes = cmds.listRelatives(
        driver, shapes=True, type="mesh",
        noIntermediate=True, fullPath=True,
    ) or []

    if not driver_shapes:
        return None, None

    driver_shape = driver_shapes[0]

    # Determine base mesh strategy
    base_dup = None
    if use_base_duplicate:
        base_name = "{}_wrapBase".format(
            driver.split("|")[-1]
        )
        base_dup = cmds.duplicate(
            driver, returnRootsOnly=True,
            inputConnections=False, name=base_name,
        )[0]

        # Unlock transforms on base duplicate
        for attr in (
            "translateX", "translateY", "translateZ",
            "rotateX", "rotateY", "rotateZ",
            "scaleX", "scaleY", "scaleZ",
        ):
            try:
                cmds.setAttr(
                    "{}.{}".format(base_dup, attr),
                    lock=False,
                )
            except RuntimeError:
                pass

        cmds.delete(base_dup, constructionHistory=True)
        cmds.setAttr(
            "{}.visibility".format(base_dup), 0
        )

        base_shapes = cmds.listRelatives(
            base_dup, shapes=True, type="mesh",
            fullPath=True,
        ) or []
        if not base_shapes:
            cmds.delete(base_dup)
            return None, None

        base_shape = base_shapes[0]
    else:
        # Use driver's intermediate (orig) shape
        all_shapes = cmds.listRelatives(
            driver, shapes=True, type="mesh",
            fullPath=True,
        ) or []
        orig_shapes = [
            s for s in all_shapes
            if cmds.getAttr(
                "{}.intermediateObject".format(s)
            )
        ]
        if orig_shapes:
            base_shape = orig_shapes[0]
        else:
            base_shape = driver_shape

    # Create wrap deformer
    wrap_name = name or "wrap"
    wrap = cmds.deformer(
        target, type="wrap", name=wrap_name
    )[0]
    cmds.setAttr("{}.exclusiveBind".format(wrap), 1)
    cmds.setAttr(
        "{}.autoWeightThreshold".format(wrap), 1
    )
    cmds.setAttr("{}.dropoff[0]".format(wrap), 4.0)
    cmds.setAttr("{}.inflType[0]".format(wrap), 2)

    # Connect base mesh
    cmds.connectAttr(
        "{}.worldMesh[0]".format(base_shape),
        "{}.basePoints[0]".format(wrap),
        force=True,
    )

    # Connect driver (visible/deformed shape)
    cmds.connectAttr(
        "{}.outMesh".format(driver_shape),
        "{}.driverPoints[0]".format(wrap),
        force=True,
    )

    # Connect geometry matrix
    cmds.connectAttr(
        "{}.worldMatrix[0]".format(target),
        "{}.geomMatrix".format(wrap),
        force=True,
    )

    return wrap, base_dup


def create_cluster_on_curve(curve, control_points=None):
    """
    在给定曲线的指定控制点上创建簇变形器。

    参数:
        curve (str or PyNode): 要应用簇变形器的曲线名称或PyNode。
        control_points (list of int, optional): 要影响的控制点索引列表。
            如果为None则应用于所有控制点。默认为None。

    返回:
        tuple: 簇名称和簇手柄名称。
    """
    # Check if curve is a PyNode, if not make it one
    if not isinstance(curve, pm.nt.Transform):
        curve = pm.PyNode(curve)

    # If control_points is None, apply cluster to the entire curve
    if control_points is None:
        cluster_node, cluster_handle = pm.cluster(curve)
    else:
        # Generate list representing the control points on the curve
        control_points_list = [
            "{}.cv[{}]".format(curve, i) for i in control_points
        ]

        # Create the cluster deformer
        cluster_node, cluster_handle = pm.cluster(control_points_list)

    return cluster_node, cluster_handle


def create_proximity_wrap(
    target_geos,
    driver_geos,
    deformer_name=None,
    weights_path=None,
    weights_filename=None,
    smoothInfluences=0,

):
    """
    创建邻近包裹变形器。

    参数:
        target_geos: 要变形的单个几何体或几何体列表（字符串或PyNode）
        driver_geos: 单个驱动器几何体或驱动器列表（字符串或PyNode）
        deformer_name: 变形器的可选名称。如果为None，则从第一个目标几何体生成。
        weights_path: 权重文件目录的可选路径
        weights_filename: 权重文件的可选文件名（默认为deformer_name + ".json"）

    返回:
        重命名后的变形器节点名称
    """
    # Ensure lists
    if not isinstance(target_geos, (list, tuple)):
        target_geos = [target_geos]
    if not isinstance(driver_geos, (list, tuple)):
        driver_geos = [driver_geos]

    # Convert strings to PyNodes
    target_geos = [pm.PyNode(geo) if isinstance(geo, str) else geo for geo in target_geos]
    driver_geos = [pm.PyNode(geo) if isinstance(geo, str) else geo for geo in driver_geos]

    # Generate deformer name if not provided
    if deformer_name is None:
        base_name = target_geos[0].name().split("|")[-1].split(":")[-1]
        deformer_name = f"{base_name}_proximityWrap"

    # Create the proximity wrap deformer on all target geos
    target_names = [geo.name() for geo in target_geos]
    d = cmds.deformer(target_names, type="proximityWrap")
    pwni = ifc.NodeInterface(d[0])

    # Add all drivers (Maya 2023 changed method name to addDrivers)
    for driver_geo in driver_geos:
        try:
            pwni.addDriver(driver_geo.getShape().name())
        except AttributeError:
            pwni.addDrivers(driver_geo.getShape().name())

    pm.rename(d[0], deformer_name)

    # Import weights if path is provided
    if weights_path is not None:
        filename = weights_filename if weights_filename else f"{deformer_name}.json"
        pm.deformerWeights(
            filename,
            im=True,
            method="index",
            deformer=deformer_name,
            path=weights_path,
        )

    cmds.setAttr(f"{deformer_name}.smoothInfluences", smoothInfluences)

    return deformer_name


# =============================================================================
# WIRE DEFORMER FUNCTIONS
# =============================================================================


def createWireDeformer(mesh, curve, dropoffDistance=1.0, name="wire"):
    """使用曲线在网格上创建线变形器。

    参数:
        mesh (str): 目标网格名称。
        curve (str): 驱动曲线名称。
        dropoffDistance (float): 线影响的衰减距离。
            默认为1.0。
        name (str): 线变形器的名称。默认为"wire"。

    返回:
        str: 创建的线变形器名称，失败时返回None。

    示例:
        >>> wire = createWireDeformer("pSphere1", "curve1", dropoffDistance=5.0)
    """
    wire_result = cmds.wire(
        mesh,
        wire=curve,
        name=name,
        groupWithBase=False,
        envelope=1.0,
        crossingEffect=0,
        localInfluence=0,
        dropoffDistance=(0, dropoffDistance),
    )

    wire_deformer = wire_result[0] if wire_result else None

    # Set rotation to 0 to prevent twisting
    if wire_deformer:
        cmds.setAttr(wire_deformer + ".rotation", 0)

    return wire_deformer


def getWireDeformerInfo(wireDeformer):
    """获取线变形器信息。

    从线变形器节点检索线曲线、基础曲线和关键属性。

    参数:
        wireDeformer (str): 线变形器节点名称。

    返回:
        dict: 包含线信息的字典，失败时返回None。
            键:
                - wire_curve (str): 变形/动画曲线
                - base_curve (str): 原始未变形曲线
                - dropoff_distance (float): 线影响衰减距离
                - scale (float): 线缩放乘数
                - envelope (float): 线封套值

    示例:
        >>> info = getWireDeformerInfo("wire1")
        >>> print(info["dropoff_distance"])
        5.0
    """
    if not wireDeformer or not cmds.objExists(wireDeformer):
        cmds.warning("线变形器不存在: {}".format(wireDeformer))
        return None

    wire_curve = None
    base_curve = None

    # Try to get the deformed wire curve
    deformed_connections = cmds.listConnections(
        wireDeformer + ".deformedWire",
        source=True,
        destination=False,
        shapes=True,
    )

    if deformed_connections:
        for conn in deformed_connections:
            if cmds.nodeType(conn) == "nurbsCurve":
                parents = cmds.listRelatives(conn, parent=True, fullPath=True)
                if parents:
                    wire_curve = parents[0]
                else:
                    wire_curve = conn
                break
            elif cmds.nodeType(conn) == "transform":
                wire_curve = conn
                break

    # If still not found, try baseWire
    if not wire_curve:
        base_connections = cmds.listConnections(
            wireDeformer + ".baseWire",
            source=True,
            destination=False,
            shapes=True,
        )
        if base_connections:
            for conn in base_connections:
                if cmds.nodeType(conn) == "nurbsCurve":
                    parents = cmds.listRelatives(conn, parent=True, fullPath=True)
                    if parents:
                        wire_curve = parents[0]
                    else:
                        wire_curve = conn
                    break

    # Try to find base curve
    base_wire_conn = cmds.listConnections(
        wireDeformer + ".baseWire",
        source=True,
        destination=False,
        shapes=True,
    )
    if base_wire_conn:
        for conn in base_wire_conn:
            if cmds.nodeType(conn) == "nurbsCurve":
                parents = cmds.listRelatives(conn, parent=True, fullPath=True)
                if parents:
                    base_curve = parents[0]
                else:
                    base_curve = conn
                break

    # Get dropoff distance
    try:
        dropoff_distance = cmds.getAttr(wireDeformer + ".dropoffDistance[0]")
        if isinstance(dropoff_distance, list):
            dropoff_distance = dropoff_distance[0] if dropoff_distance else 1.0
    except Exception:
        dropoff_distance = 1.0

    # Get scale
    try:
        scale = cmds.getAttr(wireDeformer + ".scale[0]")
        if isinstance(scale, list):
            scale = scale[0] if scale else 1.0
    except Exception:
        scale = 1.0

    # Get envelope
    try:
        envelope = cmds.getAttr(wireDeformer + ".envelope")
    except Exception:
        envelope = 1.0

    return {
        "wire_curve": wire_curve,
        "base_curve": base_curve,
        "dropoff_distance": dropoff_distance,
        "scale": scale,
        "envelope": envelope,
    }


def getWireWeightMap(mesh, wireDeformer):
    """获取线变形器的逐顶点权重映射。

    检索受线变形器影响的每个顶点的权重值。
    权重1.0表示完全影响，0.0表示无影响。

    参数:
        mesh (str): 网格名称。
        wireDeformer (str): 线变形器名称。

    返回:
        dict: 将顶点索引映射到权重值（0.0到1.0）的字典。

    示例:
        >>> weights = getWireWeightMap("pSphere1", "wire1")
        >>> print(weights[0])  # 顶点0的权重
        1.0
    """
    num_verts = cmds.polyEvaluate(mesh, vertex=True)
    weights = {}

    # Find the geometry index for this mesh
    geometry_index = 0
    try:
        output_geom = cmds.listConnections(
            wireDeformer + ".outputGeometry",
            source=False,
            destination=True,
            plugs=True,
        )
        if output_geom:
            for i, conn in enumerate(output_geom):
                if mesh in conn or mesh.split("|")[-1] in conn:
                    geometry_index = i
                    break
    except Exception:
        pass

    # Try to get weights from the deformer
    for v_idx in range(num_verts):
        try:
            weight_attr = "{}.weightList[{}].weights[{}]".format(
                wireDeformer, geometry_index, v_idx
            )
            if cmds.objExists(weight_attr):
                w = cmds.getAttr(weight_attr)
                weights[v_idx] = w if w is not None else 1.0
            else:
                weights[v_idx] = 1.0
        except Exception:
            weights[v_idx] = 1.0

    return weights


def getMeshWireDeformers(mesh):
    """获取影响网格的所有线变形器。

    在网格的变形历史中搜索线变形器节点。

    参数:
        mesh (str): 网格名称。

    返回:
        list: 线变形器名称列表，未找到则返回空列表。

    示例:
        >>> wires = getMeshWireDeformers("pSphere1")
        >>> print(wires)
        ['wire1', 'wire2']
    """
    history = cmds.listHistory(mesh, pruneDagObjects=True) or []
    wires = [h for h in history if cmds.nodeType(h) == "wire"]
    return wires
