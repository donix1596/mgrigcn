
# imports
from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtWidgets

class QCollapse(QtWidgets.QWidget):

    SPEED = 150

    def __init__(self, parent=None, title="QCollapse"):
        """ QCollapse 是一个带过渡效果的可折叠部件

        Args:
            parent (QWidget): QCollapseWidget 的父级部件
            title (str): 部件的标题名称
        """

        super(QCollapse, self).__init__(parent=parent)

        # create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # create arrow button
        self.arrow_button = QtWidgets.QToolButton()
        self.arrow_button.setToolButtonStyle(
            QtCore.Qt.ToolButtonTextBesideIcon)
        self.arrow_button.setArrowType(QtCore.Qt.RightArrow)
        self.arrow_button.setText(title)
        self.arrow_button.setCheckable(True)
        self.arrow_button.setChecked(False)

        # 创建可折叠滚动区域。这将使用布局来容纳内容
        self.scrool_area = QtWidgets.QScrollArea()
        self.scrool_area.setFrameStyle(6)
        self.scrool_area.setMinimumHeight(0)
        self.scrool_area.setMaximumHeight(0)
        self.scrool_area.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                       QtWidgets.QSizePolicy.Fixed)

        # 添加部件到布局
        main_layout.addWidget(self.arrow_button)
        main_layout.addWidget(self.scrool_area)

        # creates animation group
        self.animation_group = QtCore.QParallelAnimationGroup()

        # 声明属性以展开 QCollapse 部件
        self.animation_group.addAnimation(QtCore.QPropertyAnimation(
                                          self, b"minimumHeight"))
        self.animation_group.addAnimation(QtCore.QPropertyAnimation(
                                          self, b"maximumHeight"))
        # 声明属性以展开滚动区域部件
        self.animation_group.addAnimation(QtCore.QPropertyAnimation(
                                          self.scrool_area, b"maximumHeight"))

        # adds signal connection
        self.arrow_button.clicked.connect(self.__run_animation)

    def __run_animation(self):
        """运行动画组
        """

        # set arrow and animation direction state
        if self.arrow_button.isChecked():
            self.arrow_button.setArrowType(QtCore.Qt.DownArrow)
            self.animation_group.setDirection(QtCore.QAbstractAnimation.Forward)
        else:
            self.arrow_button.setArrowType(QtCore.Qt.RightArrow)
            self.animation_group.setDirection(QtCore.QAbstractAnimation.Backward)

        # starts animation
        self.animation_group.start()

    def set_layout(self, layout):
        """将给定布局应用到滚动区域部件

        Args:
            layout (QLayout): 添加到 QCollapse 中的布局部件
        """

        # sets the layout into the scroll area
        self.scrool_area.setLayout(layout)

        # queries widget height values
        collapse_height = (self.sizeHint().height() -
                           self.scrool_area.maximumHeight())
        content_height = layout.sizeHint().height()

        # set transition
        for i in range(self.animation_group.animationCount() - 1):
            _anim = self.animation_group.animationAt(i)
            _anim.setDuration(self.SPEED)
            _anim.setStartValue(collapse_height)
            _anim.setEndValue(collapse_height + content_height)

        animated_content = self.animation_group.animationAt(
            self.animation_group.animationCount() - 1)
        animated_content.setDuration(self.SPEED)
        animated_content.setStartValue(0)
        animated_content.setEndValue(content_height)
