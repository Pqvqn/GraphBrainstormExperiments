import sys

from PyQt5.QtCore import Qt, QEvent, QSize, QDir, QChildEvent
from PyQt5.QtGui import QFont, QKeyEvent
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout, QLabel, QFrame, QSpacerItem, \
    QHBoxLayout, QScrollArea, QPushButton, QDialog, QPlainTextEdit, QFileDialog


class Model():

    Alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

    def __init__(self, filepath="", root_string=""):

        if filepath == "":
            self.root = Post(None)
            self.root.init_content([root_string])
        else:
            self.above_file = None
            if root_string != "":
                self.above_file = Post(None)
                self.above_file.init_content([root_string])

            self.root = self.load_file(filepath, true_root = self.above_file)


    def load_file(self, filepath, true_root = None):
        content = {}
        nodes = {}
        curr_node = None
        indent_level = 0
        root = None
        with open(filepath, 'r') as tree_file:
            for line in tree_file:
                line = line.rstrip().replace('\\n', '\n')
                parent = curr_node
                ind = 0
                while line[0] == '\t':
                    line = line[1:]
                    ind += 1

                diff = indent_level - ind
                if diff < -1:
                    raise Exception("Overindented line in tree file")
                elif diff >= 0:
                    if parent is None:
                        parent = true_root
                    else:
                        for i in range(diff + 1):
                            parent = parent.parent
                indent_level = ind

                splitline = line.split(" ", 1)
                label = splitline[0]
                parts = splitline[1].split(">")
                content[label] = []
                for p in range(len(parts)):
                    if p == 0:
                        content[label].append(parts[p])
                    else:
                        content[label].extend(parts[p].split(" ", 1))

                if parent is None:
                    curr_node = Post(None)
                    root = curr_node
                else:
                    curr_node = parent.make_child()

                nodes[label] = curr_node

        for label in content.keys():
            content_list = []
            alternate = False
            for p in content[label]:
                if alternate:
                    content_list.append(nodes[p])
                else:
                    content_list.append(p)
                alternate = not alternate
            nodes[label].init_content(content_list)

        if root is None:
            return true_root
        else:
            return root

    def write_to(self, path):
        labels = {}

        def add_labels(node, label_dict):
            if node.parent is None:
                label_dict[node] = "0"
            else:
                parent_label = label_dict[node.parent]
                child_num = node.parent.children.index(node)
                label_dict[node] = parent_label + Model.Alphabet[child_num]

            for c in node.children:
                if c is not None:
                    add_labels(c, label_dict)

        add_labels(self.root, labels)

        def write_nodes(file, node, label_dict, indent):
            line = "\t" * indent + label_dict[node] + " "
            for element in node.content:
                if isinstance(element, str):
                    line += element
                elif isinstance(element, Post):
                    line += ">" + label_dict[element] + " "
            line = line.replace('\n', '\\n')
            file.write(line + "\n")

            for c in node.children:
                if c is not None:
                    write_nodes(file, c, label_dict, indent+1)

        with open(path, 'w') as file_dest:
            write_nodes(file_dest, self.root, labels, 0)


    @staticmethod
    def up(post):
        if post is None:
            return None
        return post.parent

    @staticmethod
    def side(offset, post):
        if post is None:
            return None
        if post.parent is None:
            return None
        new_idx = (post.parent.children.index(post) + offset) % len(post.parent.children)
        return post.parent.children[new_idx]

    @staticmethod
    def down(chosen, post):
        if post is None:
            return None
        return post.children[chosen]

class Post():

    def __init__(self, parent):

        self.parent = parent
        self.content = None
        self.children = [None]

    def init_content(self, new_content):
        if self.content is not None:
            raise Exception("Post contents cannot be changed")
        self.content = new_content

    def make_child(self):
        child = Post(self)
        self.children.insert(-1, child)
        return child



class View(QMainWindow):

    def __init__(self):
        super(QMainWindow, self).__init__()

        self.setWindowTitle("Brainstormer Prototype")

        widget = QWidget()
        self.setCentralWidget(widget)
        h_layout = QHBoxLayout()
        widget.setLayout(h_layout)
        self.sidebar = Sidebar(self)
        self.main_grid = MainGrid(self)
        h_layout.addWidget(self.sidebar)
        h_layout.addWidget(self.main_grid)
        self.showMaximized()

        self.model = None

    def load_model(self, model):
        self.main_grid.load_model(model)
        self.sidebar.clear_pins()
        self.model = model

    def keyReleaseEvent(self, event):
        if isinstance(event, QKeyEvent) and self.model is not None:
            if event.key() == Qt.Key_Down:
                self.main_grid.move_down()
            elif event.key() == Qt.Key_Right:
                self.main_grid.move_right()
            elif event.key() == Qt.Key_Left:
                self.main_grid.move_left()
            elif event.key() == Qt.Key_Up:
                self.main_grid.move_up()
            elif event.key() == Qt.Key_Shift:
                self.main_grid.next_embed()
            elif event.key() == Qt.Key_Space:
                self.main_grid.select_embed()
            elif event.key() == Qt.Key_Backspace:
                self.main_grid.go_back()


class MainGrid(QWidget):

    def __init__(self, view):
        super(QWidget, self).__init__()

        self.view = view

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        for i in range(3):
            for j in range(3):
                view_type = PostWidget.ViewCentral if i==1 and j==1 else PostWidget.ViewNormal
                self.layout.addWidget(PostWidget(None, view_type, self), i*2, j*2, alignment=Qt.AlignCenter)

        def add_arrow(rnum, cnum):
            txt_opts = ["↙", "↓", "↘"]
            arrbox = QFrame()
            arrbox.setFixedSize(50, 50)
            arrbox.setFrameStyle(QFrame.Panel | QFrame.Plain)
            arrbox.setLineWidth(0)
            arrbox_layout = QHBoxLayout()
            arrbox.setLayout(arrbox_layout)
            arr = QLabel(txt_opts[cnum])
            arr.setFont(QFont('Arial', 20))
            arrbox_layout.addWidget(arr)
            self.layout.addWidget(arrbox, rnum*2+1, cnum+1, alignment=Qt.AlignCenter)
            return arr

        self.arrows = [[],[]]
        for i in range(len(self.arrows)):
            for j in range(3):
                arr = add_arrow(i, j)
                self.arrows[i].append(arr)


    def load_model(self, model):
        self.under_thread = []
        self.prev_stack = []
        self.view_post(model.root)

    def clear_grid(self):
        for i in range(3):
            for j in range(3):
                self.layout.itemAtPosition(i*2, j*2).widget().deleteLater()
        for i in range(2):
            for j in range(3):
                self.arrows[i][j].hide()

    def under_index(self):
        return self.under_thread[-1] if len(self.under_thread) > 0 else 0

    def view_post(self, post):
        self.clear_grid()
        post_grid = [[Model.side(-1, Model.up(post)), Model.up(post), Model.side(1, Model.up(post))],
                     [Model.side(-1, post), post, Model.side(1, post)],
                     [Model.side(-1, Model.down(self.under_index(), post)), Model.down(self.under_index(), post),
                      Model.side(1, Model.down(self.under_index(), post))]]
        for i in range(3):
            for j in range(3):
                view_type = PostWidget.ViewCentral if i==1 and j==1 else PostWidget.ViewNormal
                self.layout.addWidget(PostWidget(post_grid[i][j], view_type, self), i*2, j*2, alignment=Qt.AlignCenter)

        for i in range(2):
            for j in range(3):
                if post_grid[i+1][j] is not None and post_grid[i][1] is not None:
                    self.arrows[i][j].show()

        self.current_post = post
        self.embed_highlight = -1
        self.prev_stack.append(post)
        if len(self.prev_stack) > 10:
            self.prev_stack.pop(0)

    def move_up(self):
        up_post = Model.up(self.current_post)
        if up_post is not None:
            self.under_thread.append(up_post.children.index(self.current_post))
            self.view_post(up_post)

    def move_left(self):
        left_post = Model.side(-1, self.current_post)
        if left_post is not None:
            self.under_thread.clear()
            self.view_post(left_post)

    def move_right(self):
        right_post = Model.side(1, self.current_post)
        if right_post is not None:
            self.under_thread.clear()
            self.view_post(right_post)

    def move_down(self):
        chosen = self.under_index()
        down_post = Model.down(chosen, self.current_post)
        if down_post is not None:
            if len(self.under_thread) > 0:
                self.under_thread.pop()
            self.view_post(down_post)

    def next_embed(self):
        embeds = [x for x in self.current_post.content if isinstance(x, Post)]
        if len(embeds) > 0:
            self.embed_highlight += 1
            if self.embed_highlight >= len(embeds):
                self.embed_highlight = -1
            self.layout.itemAtPosition(2, 2).widget().switch_embed_selection(self.embed_highlight)

    def select_embed(self):
        embeds = [x for x in self.current_post.content if isinstance(x, Post)]
        if len(embeds) > 0:
            next = 0
            if self.embed_highlight > 0:
                next = self.embed_highlight
            self.jump_to(embeds[next])

    def pin_post(self, post):
        self.view.sidebar.pin(post)

    def jump_to(self, post):
        self.under_thread.clear()
        self.view_post(post)

    def go_back(self):
        if len(self.prev_stack) > 1:
            self.prev_stack.pop()
            self.jump_to(self.prev_stack.pop())

class PostWidget(QFrame):

    ViewEmbed = 0
    ViewNormal = 1
    ViewCentral = 2
    ViewPinned = 3
    ViewInert = 4
    Dimensions = [QSize(375, 125), QSize(450, 200), QSize(500, 350), QSize(250, 100), QSize(250, 100)]
    Fonts = [QFont('Arial', 15), QFont('Arial', 15), QFont('Arial', 20), QFont('Arial', 10), QFont('Arial', 10)]

    def __init__(self, post, view_type, grid):
        super(QFrame, self).__init__()

        self.setFixedSize(PostWidget.Dimensions[view_type])
        self.embeds = []
        self.post = post
        self.view_type = view_type
        self.grid = grid

        if post is not None:
            content_layout = QVBoxLayout()
            content_layout.setAlignment(Qt.AlignTop)

            for x in post.content:
                if isinstance(x, str):
                    text = QLabel(x)
                    text.setFont(PostWidget.Fonts[view_type])
                    text.setIndent(20)
                    text.setWordWrap(True)
                    text.setFixedWidth(PostWidget.Dimensions[view_type].width() - 50)
                    content_layout.addWidget(text)
                elif isinstance(x, Post):
                    embed_view_type = PostWidget.ViewInert if (view_type == PostWidget.ViewPinned or view_type ==
                                                                PostWidget.ViewInert) else PostWidget.ViewEmbed
                    embed = PostWidget(x, embed_view_type, grid)
                    self.embeds.append(embed)
                    content_layout.addWidget(embed)
                else:
                    raise Exception("Unknown type of content: "+x)

            content_layout.addStretch()
            content_container = QWidget()
            content_container.setLayout(content_layout)
            layout = QVBoxLayout()

            top_bar = QHBoxLayout()

            if view_type == PostWidget.ViewPinned:
                unpin_button = QPushButton("❌")
                unpin_button.setFixedSize(30, 30)
                unpin_button.setFlat(True)
                unpin_button.pressed.connect(self.deleteLater)
                top_bar.addWidget(unpin_button, alignment=Qt.AlignRight)
            elif view_type != PostWidget.ViewInert:
                pin_button = QPushButton("📌")
                pin_button.setFixedSize(30, 30)
                pin_button.setFlat(True)
                pin_button.pressed.connect(lambda: grid.pin_post(post))
                top_bar.addWidget(pin_button, alignment=Qt.AlignRight)

            layout.addLayout(top_bar)

            scroll = QScrollArea()
            scroll.setWidget(content_container)
            scroll.setWidgetResizable(False)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(scroll)
            if view_type != PostWidget.ViewCentral:
                scroll.verticalScrollBar().setEnabled(False)
                scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.horizontalScrollBar().setEnabled(False)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

            if view_type == PostWidget.ViewEmbed or view_type == PostWidget.ViewPinned or view_type == PostWidget.ViewInert:
                self.setLineWidth(1)
            else:
                self.setLineWidth(2)

            self.setFrameStyle(QFrame.Box)
            self.setLayout(layout)

            self.current_highlight = -1

            if view_type != PostWidget.ViewInert:
                self.setAttribute(Qt.WA_NoMousePropagation)

            self.highlighted = False

    def switch_embed_selection(self, index):
        if self.current_highlight >= 0:
            self.embeds[self.current_highlight].highlight(False)
        if index >= 0:
            self.embeds[index].highlight(True)
        self.current_highlight = index

    def highlight(self, on=True):
        if on:
            self.setStyleSheet('background-color: rgb(200,200,200)')
        else:
            self.setStyleSheet('')
        self.highlighted = on

    def mousePressEvent(self, event):
        if self.post is not None and self.view_type != PostWidget.ViewInert:
            if event.buttons() == Qt.LeftButton:
                self.grid.jump_to(self.post)
            elif event.buttons() == Qt.RightButton:
                self.grid.view.sidebar.insert_embed(self)


class Sidebar(QFrame):
    def __init__(self, view):
        super(QFrame, self).__init__()

        self.view = view

        self.setFrameStyle(QFrame.Box)
        self.setFixedWidth(300)

        layout = QVBoxLayout()
        self.setLayout(layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setContentsMargins(0, 0, 0, 0)

        pins = QWidget()
        self.pins_layout = QVBoxLayout()
        self.pins_layout.addStretch()
        pins.setLayout(self.pins_layout)
        scroll.setWidget(pins)
        layout.addWidget(scroll)

        new_post = QPushButton("\n➕ Reply\n")
        new_post.setFont(QFont("Arial", 15))
        new_post.pressed.connect(self.reply)
        layout.addWidget(new_post)

        file_controls = QGridLayout()
        layout.addLayout(file_controls)

        load_tree = QPushButton("Load")
        load_tree.pressed.connect(self.load_file)
        file_controls.addWidget(load_tree, 0, 0)
        new_tree = QPushButton("New")
        new_tree.pressed.connect(self.new_file)
        file_controls.addWidget(new_tree, 0, 1)
        save_tree_as = QPushButton("Save as")
        save_tree_as.pressed.connect(self.save_file_as)
        file_controls.addWidget(save_tree_as, 1, 0)
        save_tree = QPushButton("Save")
        save_tree.pressed.connect(self.save_file)
        file_controls.addWidget(save_tree, 1, 1)
        self.limit_during_popups = [new_tree, load_tree]

        self.filepath = None
        self.wip_dialog = None
        self.dialogs = []

    def clear_pins(self):
        for n in range(self.pins_layout.count() - 1):
            self.pins_layout.itemAt(n).widget().deleteLater()

    def pin(self, post):
        self.pins_layout.insertWidget(self.pins_layout.count() - 1,
                                      PostWidget(post, PostWidget.ViewPinned, self.view.main_grid), alignment=Qt.AlignTop)

    def reply(self):
        if self.view.model is None:
            self.new_file()
        else:
            dialog = WriteReplyDialog(self)
            dialog.setModal(False)
            dialog.setWindowFlags(Qt.WindowStaysOnTopHint)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            self.dialogs.append(dialog)
            dialog.finished.connect(lambda x: self.dialogs.remove(dialog))

    def new_file(self):
        dialog = WriteRootDialog(self)
        dialog.exec_()
        self.filepath = None

    def load_file(self):
        path = QFileDialog.getOpenFileName(self, "Open Tree File", QDir.homePath(), "Text file (*.txt)")[0]
        if path is not None and path != "":
            model = Model(filepath=path)
            self.view.load_model(model)
            self.filepath = path

    def save_file_as(self):
        path = QFileDialog.getSaveFileName(self, "Save Tree File", QDir.homePath(), "Text file (*.txt)")[0]
        if path is not None and path != "":
            self.view.model.write_to(path)
            self.filepath = path

    def save_file(self):
        if self.filepath is None:
            self.save_file_as()
        else:
            self.view.model.write_to(self.filepath)

    def set_wip_dialog(self, dialog):
        if dialog is None and self.wip_dialog is not None:
            for button in self.limit_during_popups:
                button.setEnabled(True)
        elif dialog is not None and self.wip_dialog is None:
            for button in self.limit_during_popups:
                button.setEnabled(False)
        self.wip_dialog = dialog

    def insert_embed(self, post):
        if self.wip_dialog is not None:
            self.wip_dialog.insert_embed(post)


class WriteRootDialog(QDialog):
    def __init__(self, sidebar):
        super(QDialog, self).__init__()
        self.setWindowTitle("Post Root")

        self.sidebar = sidebar

        layout = QVBoxLayout()
        self.setLayout(layout)

        parent_text = QLabel("Enter text for root of new tree")
        parent_text.setWordWrap(True)
        layout.addWidget(parent_text)

        self.first_text = QPlainTextEdit()
        layout.addWidget(self.first_text)

        post_button = QPushButton("Post")
        post_button.pressed.connect(self.post)
        layout.addWidget(post_button)
        post_button.setDefault(True)

        self.setSizeGripEnabled(True)

        self.enabled = True

    def post(self):
        if not self.enabled:
            return
        self.enabled = False

        model = Model(root_string=self.first_text.toPlainText())
        self.sidebar.view.load_model(model)
        self.accept()

class WriteReplyDialog(QDialog):
    def __init__(self, sidebar):
        super(QDialog, self).__init__()
        self.setWindowTitle("Post Reply")

        self.sidebar = sidebar

        layout = QVBoxLayout()
        self.setLayout(layout)

        parent_text = QLabel("↪  Replying to... ")
        parent_text.setWordWrap(True)
        layout.addWidget(parent_text)

        self.parent_disp = PostWidget(sidebar.view.main_grid.current_post, PostWidget.ViewInert, sidebar.view.main_grid)
        layout.addWidget(self.parent_disp)

        layout.addWidget(QLabel("↓"), alignment=Qt.AlignHCenter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Box)
        scroll.setContentsMargins(0, 0, 0, 0)
        post_container = QWidget()
        self.post_layout = QVBoxLayout()
        post_container.setLayout(self.post_layout)
        scroll.setWidget(post_container)
        layout.addWidget(scroll)

        first_text = QPlainTextEdit()
        self.post_layout.addWidget(first_text)
        self.post_layout.addStretch()

        post_button = QPushButton("Post")
        post_button.pressed.connect(self.post)
        layout.addWidget(post_button)
        post_button.setDefault(True)

        self.setSizeGripEnabled(True)

        self.enabled = True
        self.installEventFilter(self)
        post_container.installEventFilter(self)
        self.last_textbox = -1

    def eventFilter(self, source, event):
        if event.type() == QEvent.WindowActivate:
            self.sidebar.set_wip_dialog(self)
        elif event.type() == QEvent.WindowDeactivate:
            for elem in range(self.post_layout.count() - 1):
                textbox = self.post_layout.itemAt(elem).widget()
                if isinstance(textbox, QPlainTextEdit) and textbox.hasFocus():
                    self.last_textbox = elem
        elif event.type() == QEvent.DeferredDelete or event.type() == QEvent.Close:
            for elem in range(self.post_layout.count() - 1):
                embed = self.post_layout.itemAt(elem).widget()
                if isinstance(embed, PostWidget):
                    embed.destroyed.disconnect()
            self.sidebar.set_wip_dialog(None)
        elif event.type() == QEvent.ChildRemoved:
            for elem in range(1, self.post_layout.count() - 1):
                if isinstance(self.post_layout.itemAt(elem).widget(), QPlainTextEdit) and elem%2!=0:
                    self.remove_textbox(elem)
                    break

        return super(QDialog, self).eventFilter(source, event)

    def post(self):
        if not self.enabled:
            return
        self.enabled = False

        parent = self.parent_disp.post
        reply = parent.make_child()

        content = []
        for e in range(self.post_layout.count() - 1):
            widget = self.post_layout.itemAt(e).widget()
            if isinstance(widget, QPlainTextEdit):
                content.append(widget.toPlainText())
            elif isinstance(widget, PostWidget):
                content.append(widget.post)

        reply.init_content(content)

        self.sidebar.view.main_grid.jump_to(reply)
        self.sidebar.set_wip_dialog(None)
        self.accept()

    def insert_embed(self, post):
        if self.last_textbox >= 0:

            before_text = self.post_layout.itemAt(self.last_textbox).widget()

            cursor = before_text.textCursor().position()
            full_text = before_text.toPlainText()
            before_text.setPlainText(full_text[:cursor])

            embed_widget = PostWidget(post.post, PostWidget.ViewPinned, self.sidebar.view.main_grid)
            self.post_layout.insertWidget(self.last_textbox+1, embed_widget)
            after_text = QPlainTextEdit(full_text[cursor:])
            self.post_layout.insertWidget(self.last_textbox+2, after_text)

            self.last_textbox = -1

    def remove_textbox(self, textbox):
        if textbox == self.last_textbox:
            self.last_textbox = -1
        remove_text = self.post_layout.itemAt(textbox).widget()
        merged_text = self.post_layout.itemAt(textbox - 1).widget()
        merged_text.appendPlainText(remove_text.toPlainText())
        remove_text.deleteLater()


class App(QApplication):

    def __init__(self, argv):
            super(App, self).__init__(argv)

            self.view = View()
            self.view.show()

if __name__ == '__main__':
    app = App(sys.argv)
    sys.exit(app.exec_())