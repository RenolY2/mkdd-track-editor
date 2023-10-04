from PySide6 import QtGui, QtWidgets


class NonAutodismissibleMenu(QtWidgets.QMenu):

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        action = self.activeAction()
        if action is not None and action.isEnabled() and action.isCheckable():
            action.trigger()
            event.accept()
            return

        super().mouseReleaseEvent(event)
