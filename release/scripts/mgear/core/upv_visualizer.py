"""UPV可视化模块。

为Maya引导阶段创建极向量(UPV)可视化节点网络。
仅使用Maya 2022+中可用的节点以保持向后兼容性
(plusMinusAverage, multiplyDivide等)。
"""

import mgear.pymaya as pm
from mgear.core import node as nod


def upv_vis_decompose_nodes(root, elbow, wrist, eff):
    """为引导节点创建分解矩阵节点。

    参数:
        root (PyNode): 根引导节点。
        elbow (PyNode): 肘部引导节点。
        wrist (PyNode): 腕部引导节点。
        eff (PyNode): 末端执行器引导节点。

    返回:
        list: 四个分解矩阵节点 [root, elbow, wrist, eff]。
    """
    guide_nodes = [root, elbow, wrist, eff]
    return [
        nod.createDecomposeMatrixNode(f"{guide}.worldMatrix[0]")
        for guide in guide_nodes
    ]


def create_vector_subtraction_nodes(elbow, wrist, root, eff):
    """创建向量减法节点网络。

    使用plusMinusAverage (operation=2)替代减法节点
    以兼容Maya 2022+。

    参数:
        elbow (PyNode): 肘部引导节点。
        wrist (PyNode): 腕部引导节点。
        root (PyNode): 根引导节点。
        eff (PyNode): 末端执行器引导节点。

    返回:
        dict: 按角色键控的PMA节点。
    """
    names = {
        "crossProduct_elbow": "{}_crossProduct".format(elbow.nodeName()),
        "crossProduct_wrist": "{}_crossProduct".format(wrist.nodeName()),
        "crossProduct_root": "{}_crossProduct".format(root.nodeName()),
        "sub_elbow": elbow.nodeName(),
        "sub_wrist": wrist.nodeName(),
        "sub_eff": eff.nodeName(),
    }
    nodes = {}
    for key, name in names.items():
        n = nod.createPlusMinusAverage3D([], operation=2)
        pm.rename(n, "{}_pma".format(name))
        nodes[key] = n
    return nodes


def connect_decompose_to_vector_nodes(decompose_nodes, vector_nodes):
    """将分解矩阵节点连接到向量减法节点。

    参数:
        decompose_nodes (list): 分解矩阵节点
            [root, elbow, wrist, eff]。
        vector_nodes (dict): PMA减法节点字典。
    """
    decm = decompose_nodes
    connections = (
        # (source_for_input3D[0], source_for_input3D[1], target_key)
        (decm[2], decm[0], "crossProduct_root"),   # wrist - root
        (decm[1], decm[0], "crossProduct_elbow"),   # elbow - root
        (decm[2], decm[0], "crossProduct_wrist"),   # wrist - root
        (decm[1], decm[0], "sub_elbow"),             # elbow - root
        (decm[2], decm[0], "sub_wrist"),             # wrist - root
        (decm[3], decm[0], "sub_eff"),               # eff - root
    )
    for src_a, src_b, key in connections:
        pma = vector_nodes[key]
        pm.connectAttr(
            f"{src_a}.outputTranslate", f"{pma}.input3D[0]"
        )
        pm.connectAttr(
            f"{src_b}.outputTranslate", f"{pma}.input3D[1]"
        )


def calculate_vector_lengths(vector_nodes):
    """从PMA减法输出计算向量长度。

    参数:
        vector_nodes (dict): PMA减法节点字典。

    返回:
        dict: 按'eff', 'elbow', 'wrist'键控的长度节点。
    """
    length_nodes = {}
    for joint_name in ("eff", "elbow", "wrist"):
        # Use distanceBetween with point2 at origin to
        # compute vector length. The 'length' node only
        # exists in Maya 2024.2+.
        dist_node = pm.createNode(
            "distanceBetween",
            name="{}_vectorLength".format(joint_name),
        )
        pma = vector_nodes["sub_{}".format(joint_name)]
        pma.output3D >> dist_node.point1
        # point2 defaults to (0,0,0) — distance = length
        length_nodes[joint_name] = dist_node

    return length_nodes


def setup_math_operations(root, length_nodes, float_value=0.5):
    """设置极向量长度的数学运算节点。

    参数:
        root (PyNode): 根引导节点。
        length_nodes (dict): 长度节点字典。
        float_value (float, optional): 乘法系数。

    返回:
        tuple: (half_one_float_node, math_nodes字典)。
    """
    # Compute the maximum of a minimum floor value and three
    # vector lengths.  The 'max' node only exists in Maya
    # 2024.2+, so we chain condition nodes instead.
    min_floor = nod.createMulNode(0.010, 1.0)
    pm.rename(min_floor, "{}_max_md".format(root.nodeName()))

    # max(floor, eff)
    cond1 = nod.createConditionNode(
        firstTerm="{}.outputX".format(min_floor.name()),
        secondTerm=length_nodes["eff"].distance,
        operator=2,  # greater than
        ifTrue="{}.outputX".format(min_floor.name()),
        ifFalse=length_nodes["eff"].distance,
    )
    pm.rename(cond1, "{}_max_cond1".format(root.nodeName()))

    # max(prev, elbow)
    cond2 = nod.createConditionNode(
        firstTerm="{}.outColorR".format(cond1.name()),
        secondTerm=length_nodes["elbow"].distance,
        operator=2,
        ifTrue="{}.outColorR".format(cond1.name()),
        ifFalse=length_nodes["elbow"].distance,
    )
    pm.rename(cond2, "{}_max_cond2".format(root.nodeName()))

    # max(prev, wrist)
    cond3 = nod.createConditionNode(
        firstTerm="{}.outColorR".format(cond2.name()),
        secondTerm=length_nodes["wrist"].distance,
        operator=2,
        ifTrue="{}.outColorR".format(cond2.name()),
        ifFalse=length_nodes["wrist"].distance,
    )
    pm.rename(cond3, "{}_max_cond3".format(root.nodeName()))

    half_one_float_node = nod.createMulNode(
        "{}.outColorR".format(cond3.name()), float_value
    )
    pm.rename(
        half_one_float_node, "{}_half_one_md".format(root.nodeName())
    )

    math_nodes = {
        "max_chain": [cond1, cond2, cond3],
        "half_multiply": half_one_float_node,
    }

    return half_one_float_node, math_nodes


def setup_cross_product_chain(root, elbow, wrist, vector_nodes, float_value):
    """设置叉积计算链。

    参数:
        root (PyNode): 根引导节点。
        elbow (PyNode): 肘部引导节点。
        wrist (PyNode): 腕部引导节点。
        vector_nodes (dict): PMA向量节点字典。
        float_value (float): 长度计算系数。

    返回:
        tuple: (normalize_node, half_multiply_node, math_nodes)。
    """
    length_nodes = calculate_vector_lengths(vector_nodes)
    half_multiply_node, math_nodes = setup_math_operations(
        root, length_nodes, float_value
    )

    # Use vectorProduct nodes instead of normalize/crossProduct
    # which only exist in Maya 2024.2+.
    # vectorProduct operation: 0=none, 1=dot, 2=cross, 3=vectorMatrixProduct
    # normalizeOutput=True gives us normalized result.

    # Normalize elbow and wrist cross products
    normalize_elbow = pm.createNode(
        "vectorProduct",
        name="{}_normalize".format(elbow.nodeName()),
    )
    normalize_elbow.operation.set(0)
    normalize_elbow.normalizeOutput.set(True)
    vector_nodes["crossProduct_elbow"].output3D >> normalize_elbow.input1

    normalize_wrist = pm.createNode(
        "vectorProduct",
        name="{}_normalize".format(wrist.nodeName()),
    )
    normalize_wrist.operation.set(0)
    normalize_wrist.normalizeOutput.set(True)
    vector_nodes["crossProduct_wrist"].output3D >> normalize_wrist.input1

    # Cross product: wrist x elbow
    crossProduct_wrist_elbow = pm.createNode(
        "vectorProduct",
        name="{}_crossProduct_wrist_elbow".format(root.nodeName()),
    )
    crossProduct_wrist_elbow.operation.set(2)
    normalize_wrist.output >> crossProduct_wrist_elbow.input1
    normalize_elbow.output >> crossProduct_wrist_elbow.input2

    # Default cross product (elbow x -Z)
    crossProduct_default = pm.createNode(
        "vectorProduct",
        name="{}_crossProduct_default".format(root.nodeName()),
    )
    crossProduct_default.operation.set(2)
    crossProduct_default.input2Z.set(-1.000)
    normalize_elbow.output >> crossProduct_default.input1

    # Sum cross product components to check if zero
    cp_sum_node = nod.createPlusMinusAverage1D(
        [
            "{}.outputX".format(crossProduct_wrist_elbow),
            "{}.outputY".format(crossProduct_wrist_elbow),
            "{}.outputZ".format(crossProduct_wrist_elbow),
        ],
        operation=1,
    )
    pm.rename(
        cp_sum_node,
        "{}_crossProduct_wrist_elbow_sum".format(root.nodeName()),
    )

    condition_node = pm.createNode(
        "condition",
        name="{}_condition".format(root.nodeName()),
    )
    condition_node.secondTerm.set(0.000)

    cp_sum_node.output1D >> condition_node.firstTerm
    crossProduct_default.output >> condition_node.colorIfTrue
    crossProduct_wrist_elbow.output >> condition_node.colorIfFalse

    # Normalize condition output
    normalize_condition_node = pm.createNode(
        "vectorProduct",
        name="{}_normalize_condition".format(root.nodeName()),
    )
    normalize_condition_node.operation.set(0)
    normalize_condition_node.normalizeOutput.set(True)
    condition_node.outColor >> normalize_condition_node.input1

    # Final cross product: condition x root
    crossProduct_root = pm.createNode(
        "vectorProduct",
        name="{}_crossProduct_root".format(root.nodeName()),
    )
    crossProduct_root.operation.set(2)
    normalize_condition_node.output >> crossProduct_root.input1
    vector_nodes["crossProduct_root"].output3D >> crossProduct_root.input2

    # Normalize final result
    crossProduct_root_normalize_node = pm.createNode(
        "vectorProduct",
        name="{}_crossProduct_root_normalize".format(root.nodeName()),
    )
    crossProduct_root_normalize_node.operation.set(0)
    crossProduct_root_normalize_node.normalizeOutput.set(True)
    crossProduct_root.output >> crossProduct_root_normalize_node.input1

    return crossProduct_root_normalize_node, half_multiply_node, math_nodes


def setup_upv_position_calculation(
    elbow, upv, normalize_node, half_multiply_node, decompose_nodes
):
    """计算最终的UPV位置。

    参数:
        elbow (PyNode): 肘部引导节点。
        upv (PyNode): 极向量引导节点。
        normalize_node (PyNode): 归一化叉积节点。
        half_multiply_node (PyNode): 长度乘法节点。
        decompose_nodes (list): 分解矩阵节点列表。
    """
    upv_mul = nod.createMulNode(
        [
            f"{normalize_node}.outputX",
            f"{normalize_node}.outputY",
            f"{normalize_node}.outputZ",
        ],
        [
            f"{half_multiply_node}.outputX",
            f"{half_multiply_node}.outputX",
            f"{half_multiply_node}.outputX",
        ],
    )
    pm.rename(upv_mul, "{}_upv_pos_multiply".format(elbow.nodeName()))

    upv_sum = nod.createPlusMinusAverage3D(
        [
            "{}.output".format(upv_mul),
            "{}.outputTranslate".format(decompose_nodes[1]),
        ],
        operation=1,
    )
    pm.rename(upv_sum, "{}_upv_pos_pma".format(elbow.nodeName()))

    upv_sum.output3Dx >> upv.translateX
    upv_sum.output3Dy >> upv.translateY
    upv_sum.output3Dz >> upv.translateZ


def setup_visibility_and_matrix(root, root_decompose, upv, upvcrv):
    """设置可见性和矩阵连接。

    参数:
        root (PyNode): 根引导节点。
        root_decompose (PyNode): 来自根的分解矩阵节点。
        upv (PyNode): 极向量引导节点。
        upvcrv (PyNode): 极向量显示曲线。
    """
    root_decompose.outputScale >> upv.scale
    root.worldInverseMatrix[0] >> upv.offsetParentMatrix
    root.worldInverseMatrix[0] >> upvcrv.offsetParentMatrix


def create_upv_system(root, elbow, wrist, eff, upvcrv, upv, float_value=0.5):
    """创建完整的UPV可视化系统。

    参数:
        root (PyNode): 根引导节点。
        elbow (PyNode): 肘部引导节点。
        wrist (PyNode): 腕部引导节点。
        eff (PyNode): 末端执行器引导节点。
        upvcrv (PyNode): 极向量显示曲线节点。
        upv (PyNode): 极向量引导节点。
        float_value (float, optional): 极向量长度系数。
    """
    decompose_nodes = upv_vis_decompose_nodes(root, elbow, wrist, eff)
    if not decompose_nodes:
        return

    vector_nodes = create_vector_subtraction_nodes(elbow, wrist, root, eff)
    connect_decompose_to_vector_nodes(decompose_nodes, vector_nodes)

    normalize_node, half_multiply_node, math_nodes = (
        setup_cross_product_chain(
            root, elbow, wrist, vector_nodes, float_value
        )
    )

    setup_upv_position_calculation(
        elbow, upv, normalize_node, half_multiply_node, decompose_nodes
    )

    setup_visibility_and_matrix(root, decompose_nodes[0], upv, upvcrv)