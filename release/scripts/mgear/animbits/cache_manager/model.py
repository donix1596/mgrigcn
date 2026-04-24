
# imports
import os
from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.animbits.cache_manager.query import is_rig


class CacheManagerStringListModel(QtCore.QAbstractListModel):

    def __init__(self, items=[], parent=None):
        """缓存管理器的自定义列表模型

        Args:
            items (list): 场景内装配体的字符串列表
            parent (QtWidget): 父级部件
        """
        super(CacheManagerStringListModel, self).__init__(parent=parent)

        self.__items = items
        self.__icons_path = self.__get_resource_path()

    @staticmethod
    def __get_resource_path():
        """返回资源文件夹的相对路径
        """

        file_dir = os.path.dirname(__file__)

        if "\\" in file_dir:
            file_dir = file_dir.replace("\\", "/")

        return "{}/resources".format(file_dir)

    def data(self, index, role):
        """重写 QAbstractListModel 方法

        **data** 返回给定索引处的项目名称和图标
        """

        row = index.row()
        value = self.__items[row]

        if role == QtCore.Qt.ToolTipRole:
            return value

        if role == QtCore.Qt.DecorationRole:
            if is_rig(value):
                pixmap = QtGui.QPixmap("{}/rig.png"
                                       .format(self.__icons_path))
            else:
                pixmap = QtGui.QPixmap("{}/cache.png"
                                       .format(self.__icons_path))
            icon = QtGui.QIcon(pixmap)
            return icon

        if role == QtCore.Qt.DisplayRole:
            return value

    def rowCount(self, parent):  # @unusedVariable
        """重写 QAbstractListModel 方法

        **rowCount** 返回列表模型中的项目数量
        """

        if self.__items:
            return len(self.__items)
        else:
            return 0
