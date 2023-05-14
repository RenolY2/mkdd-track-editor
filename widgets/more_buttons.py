from PySide6 import QtWidgets

from lib.libbol import *
from widgets.tree_view import BolHeader

class MoreButtons(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self._buttons = {}
        self._target_obj = None

        self.vbox = QtWidgets.QVBoxLayout(self)
        self.vbox.setContentsMargins(0, 0, 0, 0)

        self.add_button('Add Enemy Path', 'add_enemypath')
        self.add_button('Add Enemy Points', 'add_enemypoints')
        self.add_button('Add Checkpoint Group', 'add_checkpointgroup')
        self.add_button('Add Checkpoints', 'add_checkpoints')
        self.add_button('Add Route', 'add_route')
        self.add_button('Add Route Points', 'add_routepoints')
        self.add_button('Add Starting Point', 'add_startpoint')
        self.add_button('Add Route for Object', 'route_object')

    def add_button(self, text, optionstring):
        new_button = QtWidgets.QPushButton(self)
        new_button.setText(text)
        new_button.setObjectName(optionstring)
        new_button.clicked.connect(self._on_button_clicked)

        self.vbox.addWidget(new_button)
        new_button.hide()

        self._buttons[optionstring] = new_button

    def add_buttons(self, option = None):
        self._target_obj = obj = option.bound_to if hasattr(option, 'bound_to') else None
        optionstring = None

        if isinstance(obj, EnemyPointGroups):
            optionstring = "add_enemypath"
        elif isinstance(obj, (EnemyPointGroup, EnemyPoint)):
            optionstring = "add_enemypoints"
        elif isinstance(obj, (CheckpointGroups)):
            optionstring = "add_checkpointgroup"
        elif isinstance(obj, (CheckpointGroup, Checkpoint)):
            optionstring = "add_checkpoints"
        elif isinstance(obj, ObjectContainer):
            if obj.object_type is Route:
                optionstring = "add_route"
        elif isinstance(obj, (Route, RoutePoint)):
            optionstring = "add_routepoints"
        elif isinstance(obj, KartStartPoints):
            #if len(obj.positions) == 0:
            #^ this check should be performed when/if separate battle mode support is added
            #or, someone needs to look into multiple starting points for regular courses
            #i suspect that it's useless to add more than 1 point
            optionstring = "add_startpoint"
        elif isinstance(obj, MapObject):
            if obj.route_info() == "Individual" and obj.pathid == -1:
                optionstring = "route_object"

        for name, button in self._buttons.items():
            button.setVisible(name == optionstring)

    def _on_button_clicked(self):
        if self._target_obj is None:
            return

        gen_editor = self.parent().parent().parent()
        optionstring = self.sender().objectName()
        gen_editor.button_side_button_action(optionstring, self._target_obj)
