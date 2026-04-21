from mgear.core import pyqt
from mgear.vendor.Qt import QtCore, QtWidgets
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import mgear.pymaya as pm


class SpaceRecorderUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SpaceRecorderUI, self).__init__(parent)

        # 初始化3个不同的缓冲区
        SpaceRecorderUI.world_spaces = [[], [], []]

        self.setWindowTitle("世界空间录制器")
        self.setMinimumWidth(275)
        self.setWindowFlags(QtCore.Qt.Tool)

        # 关闭时删除UI以避免winEvent错误
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        self.record_A_btn = QtWidgets.QPushButton("录制缓冲区 A")
        self.apply_A_btn = QtWidgets.QPushButton("应用缓冲区 A")
        self.apply_A_selected_btn = QtWidgets.QPushButton("应用选中缓冲区 A")

        self.record_B_btn = QtWidgets.QPushButton("录制缓冲区 B")
        self.apply_B_btn = QtWidgets.QPushButton("应用缓冲区 B")
        self.apply_B_selected_btn = QtWidgets.QPushButton("应用选中缓冲区 B")

        self.record_C_btn = QtWidgets.QPushButton("录制缓冲区 C")
        self.apply_C_btn = QtWidgets.QPushButton("应用缓冲区 C")
        self.apply_C_selected_btn = QtWidgets.QPushButton("应用选中缓冲区 C")

    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        groupBox = QtWidgets.QGroupBox()
        groupBox.setTitle("录制世界空间")
        record_layout = QtWidgets.QHBoxLayout(groupBox)
        record_layout.addWidget(self.record_A_btn)
        record_layout.addWidget(self.record_B_btn)
        record_layout.addWidget(self.record_C_btn)
        main_layout.addWidget(groupBox)

        groupBox = QtWidgets.QGroupBox()
        groupBox.setTitle("应用世界空间")
        apply_layout = QtWidgets.QHBoxLayout(groupBox)
        apply_layout.addWidget(self.apply_A_btn)
        apply_layout.addWidget(self.apply_B_btn)
        apply_layout.addWidget(self.apply_C_btn)
        main_layout.addWidget(groupBox)

        groupBox = QtWidgets.QGroupBox()
        groupBox.setTitle("应用到选择")
        apply_sel_layout = QtWidgets.QHBoxLayout(groupBox)
        apply_sel_layout.addWidget(self.apply_A_selected_btn)
        apply_sel_layout.addWidget(self.apply_B_selected_btn)
        apply_sel_layout.addWidget(self.apply_C_selected_btn)
        main_layout.addWidget(groupBox)

        main_layout.addStretch()

        self.setLayout(main_layout)

    def create_connections(self):
        self.record_A_btn.clicked.connect(SpaceRecorderUI.record_spaces_A)
        self.apply_A_btn.clicked.connect(SpaceRecorderUI.apply_spaces_A)
        self.apply_A_selected_btn.clicked.connect(
            SpaceRecorderUI.apply_to_selection_A
        )

        self.record_B_btn.clicked.connect(SpaceRecorderUI.record_spaces_B)
        self.apply_B_btn.clicked.connect(SpaceRecorderUI.apply_spaces_B)
        self.apply_B_selected_btn.clicked.connect(
            SpaceRecorderUI.apply_to_selection_B
        )

        self.record_C_btn.clicked.connect(SpaceRecorderUI.record_spaces_C)
        self.apply_C_btn.clicked.connect(SpaceRecorderUI.apply_spaces_C)
        self.apply_C_selected_btn.clicked.connect(
            SpaceRecorderUI.apply_to_selection_C
        )

    @classmethod
    def record_spaces(cls, buffer=0):
        """录制选定对象的世界空间（使用时间轴范围）

        Args:
            buffer (int, optional): 用于存储空间的缓冲区索引
        """
        cls.world_spaces[buffer] = []
        start = pm.playbackOptions(q=True, min=True)
        end = pm.playbackOptions(q=True, max=True)
        frame_range = int(end - start) + 1
        # store
        oSel = pm.selected()
        ct = start
        p_amount = 0
        increment = 100 / frame_range
        pm.progressWindow(
            title="正在录制世界空间", progress=p_amount, max=100
        )
        for i in range(frame_range):
            frame_spaces = []
            pm.progressWindow(
                e=True,
                progress=p_amount,
                status="录制帧:{} ".format(str(i)),
            )
            for x in oSel:
                pm.currentTime(int(ct))
                space = []
                space.append(x)
                space.append(x.getMatrix(worldSpace=True))
                frame_spaces.append(space)
            ct += 1
            cls.world_spaces[buffer].append(frame_spaces)
            p_amount += increment
        pm.progressWindow(e=True, endProgress=True)

    @classmethod
    def apply_spaces(cls, buffer=0):
        """应用已归档的世界空间（使用时间轴范围）

        Args:
            buffer (int, optional): 用于检索空间的缓冲区索引
        """
        if not cls.world_spaces[buffer]:
            pm.displayWarning("空间缓冲区为空。请先录制")
            return
        start = pm.playbackOptions(q=True, min=True)
        end = pm.playbackOptions(q=True, max=True)
        frame_range = int(end - start) + 1
        ct = start
        p_amount = 0
        increment = 100 / frame_range
        pm.progressWindow(
            title="正在应用世界空间", progress=p_amount, max=100
        )
        for i in range(frame_range):
            pm.currentTime(int(ct))
            frame_spaces = cls.world_spaces[buffer][i]
            pm.progressWindow(
                e=True,
                progress=p_amount,
                status="应用帧:{} ".format(str(i)),
            )
            for space in frame_spaces:
                space[0].setMatrix(space[1], worldSpace=True)
                pm.setKeyframe(space[0])
            ct += 1
            p_amount += increment
        pm.progressWindow(e=True, endProgress=True)

    @classmethod
    def apply_to_selection(cls, buffer=0):
        """将世界空间应用到选定对象（使用时间轴范围）
        选择的顺序将决定空间的使用方式，对应于存储时的选择顺序

        Args:
            buffer (int, optional): 用于检索空间的缓冲区索引
        """
        if not cls.world_spaces[buffer]:
            pm.displayWarning("空间缓冲区为空。请先录制")
            return
        oSel = pm.selected()
        if not oSel:
            pm.displayWarning("请选择对象以应用空间")
            return
        start = pm.playbackOptions(q=True, min=True)
        end = pm.playbackOptions(q=True, max=True)
        frame_range = int(end - start) + 1
        ct = start
        p_amount = 0
        increment = 100 / frame_range
        pm.progressWindow(
            title="正在应用选择世界空间", progress=p_amount, max=100
        )
        for i in range(frame_range):
            pm.currentTime(int(ct))
            frame_spaces = cls.world_spaces[buffer][i]
            for e, x in enumerate(oSel):
                frame_spaces[e][1]
                x.setMatrix(frame_spaces[e][1], worldSpace=True)
                pm.setKeyframe(x)
            ct += 1
            p_amount += increment
        pm.progressWindow(e=True, endProgress=True)

    @classmethod
    def record_spaces_A(cls):
        SpaceRecorderUI.record_spaces(buffer=0)

    @classmethod
    def record_spaces_B(cls):
        SpaceRecorderUI.record_spaces(buffer=1)

    @classmethod
    def record_spaces_C(cls):
        SpaceRecorderUI.record_spaces(buffer=2)

    @classmethod
    def apply_spaces_A(cls):
        SpaceRecorderUI.apply_spaces(buffer=0)

    @classmethod
    def apply_spaces_B(cls):
        SpaceRecorderUI.apply_spaces(buffer=1)

    @classmethod
    def apply_spaces_C(cls):
        SpaceRecorderUI.apply_spaces(buffer=2)

    @classmethod
    def apply_to_selection_A(cls):
        SpaceRecorderUI.apply_to_selection(buffer=0)

    @classmethod
    def apply_to_selection_B(cls):
        SpaceRecorderUI.apply_to_selection(buffer=1)

    @classmethod
    def apply_to_selection_C(cls):
        SpaceRecorderUI.apply_to_selection(buffer=2)


def open(*args):
    return pyqt.showDialog(SpaceRecorderUI)


if __name__ == "__main__":

    pyqt.showDialog(SpaceRecorderUI)
