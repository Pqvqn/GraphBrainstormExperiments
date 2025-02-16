import os
import random
import sys
# import ctypes
import bisect
import time

import numpy

# myappid = u'pqvqn.brainstormer.prototype.2'
# ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

from PyQt5.QtCore import Qt, QCoreApplication, QDir, pyqtSignal, QDateTime
from PyQt5.QtGui import QTextCharFormat, QTextCursor, QFont, QIcon, QColor, QBrush
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QTextEdit, QVBoxLayout, QLabel, QLineEdit, \
    QFileDialog, QInputDialog, QMessageBox, QGroupBox, QGridLayout, QCheckBox, QSpinBox, QComboBox, QDoubleSpinBox


class View(QMainWindow):

    def __init__(self, open_path=""):
        super(QMainWindow, self).__init__()

        self.window_title = "Brainstormer Second Prototype"

        # self.setWindowIcon(QIcon("...")) replace with path

        self.model = Model()
        self.saved_path = open_path
        if open_path == "":
            self.has_unsaved = False
            self.model.new_model("-")
        else:
            self.has_unsaved = False
            self.model.read_from_file(open_path)

        self.update_window_title()

        widget = QWidget()
        self.setCentralWidget(widget)
        v_layout = QVBoxLayout()
        widget.setLayout(v_layout)

        self.vis_settings = VisibilitySettings()

        doc_layout = QHBoxLayout()
        self.info_doc = InfoDoc()
        doc_layout.addWidget(self.info_doc)
        self.main_doc = MainDoc(self.model, self)
        doc_layout.addWidget(self.main_doc)

        task_layout = QHBoxLayout()
        self.write_box = WriteBox(self.model, self)
        self.author_select = QComboBox()
        self.author_select.setEditable(True)
        self.author_select.setInsertPolicy(QComboBox.InsertAtBottom)
        for a in self.model.authors:
            self.author_select.addItem(a)
        task_layout.addWidget(self.author_select)
        task_layout.addWidget(self.write_box)
        task_layout.addWidget(self.vis_settings)

        v_layout.addLayout(doc_layout)
        v_layout.addLayout(task_layout)

        self.showMaximized()

    def closeEvent(self, e):
        if self.has_unsaved:
            e.ignore()
            continue_on = self.ask_unsaved()
            if continue_on:
                e.accept()

    def change_made(self):
        if not self.has_unsaved:
            self.has_unsaved = True
            self.update_window_title()

    def update_window_title(self):
        title = os.path.basename(self.saved_path)
        if self.has_unsaved:
            title = "*"+title
        self.setWindowTitle(title + " - " + self.window_title)

    def ask_save(self):
        if self.saved_path == "":
            self.ask_save_as()
        else:
            self.model.write_to_file(self.saved_path)
            self.has_unsaved = False
            self.update_window_title()

    def ask_save_as(self):
        folder = QDir.homePath() if self.saved_path == "" else self.saved_path
        path = QFileDialog.getSaveFileName(self, "Save Graph", folder, "BUG file (*.bug)")[0]
        if path is not None and path != "":
            self.model.write_to_file(path)
            self.saved_path = path
            self.has_unsaved = False
            self.update_window_title()

    def ask_unsaved(self):

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Changes were made to the graph.\nDo you want to save your changes?")
        msg.setWindowTitle("Unsaved changes")
        msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Save)
        retval = msg.exec_()
        if retval == QMessageBox.Save:
            self.ask_save()
            return True
        elif retval == QMessageBox.Discard:
            return True
        else:
            return False

    def ask_open(self):
        if self.has_unsaved:
            continue_on = self.ask_unsaved()
            if not continue_on:
                return

        folder = QDir.homePath() if self.saved_path == "" else self.saved_path
        path = QFileDialog.getOpenFileName(self, "Open Graph", folder, "BUG file (*.bug)")[0]
        if path is not None and path != "":
            self.model.read_from_file(path)
            self.saved_path = path
            self.has_unsaved = False
            self.update_window_title()
            self.prep_new_model()

    def ask_new(self):
        if self.has_unsaved:
            continue_on = self.ask_unsaved()
            if not continue_on:
                return

        title = QInputDialog.getText(self, "New Graph Dialog", "Enter first post text:")[0]
        if title is not None and title != "":
            self.model.new_model(title, author=self.author_select.currentText())
            self.saved_path = ""
            self.has_unsaved = True
            self.update_window_title()
            self.prep_new_model()

    def prep_new_model(self):
        self.write_box.setParent(None)
        self.write_box.setDestination(None)
        self.write_box.line_edit.setText("")
        self.author_select.clear()
        for a in self.model.authors:
            self.author_select.addItem(a)
        self.main_doc.loadPage(self.model.time_ordered[0], new_doc=True)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_S and e.modifiers() & Qt.ControlModifier:
            if e.modifiers() & Qt.ShiftModifier:
                self.ask_save_as()
            else:
                self.ask_save()
        elif e.key() == Qt.Key_O and e.modifiers() & Qt.ControlModifier:
            self.ask_open()
        elif e.key() == Qt.Key_N and e.modifiers() & Qt.ControlModifier:
            self.ask_new()
        else:
            QMainWindow.keyPressEvent(self, e)

class Post:
    Suppress = -1
    Neutral = 0
    Canon = 1

    def __init__(self, ident, parent, destination, text, score=0, auxiliary=0, author="", timestamp=None):
        self.ident = ident
        self.text = text
        self.auxiliary = auxiliary
        self.score = score
        self.score_vis = self.visFromScore(self.score)
        self.canon_score = 0
        self.suppress_score = 0
        self.parent = parent
        self.destination = destination
        self.author = author
        self.timestamp = timestamp
        if parent is not None:
            parent.linkChild(self)
            if self.auxiliary != Post.Neutral:
                self.suppress_score = -1
                parent.auxFormalityChanged(self, True)
        if destination is not None:
            destination.linkSource(self)
        self.children = []
        self.sources = []

    def addScore(self, amt):
        self.score += amt
        self.score_vis = self.visFromScore(self.score)

    def visFromScore(self, score):
        return 1 / (1 + numpy.exp(-0.5 * score))

    def formality(self):
        return numpy.sign(numpy.sign(self.canon_score) - numpy.sign(self.suppress_score))

    def auxFormalityChanged(self, aux, is_upgrade):
        pre_type = self.formality()
        amt = 1 if is_upgrade else -1

        if aux.auxiliary == Post.Canon:
            self.canon_score += amt
        elif aux.auxiliary == Post.Suppress:
            self.suppress_score += amt

        post_type = self.formality()
        if self.auxiliary != Post.Neutral and self.parent is not None:
            if pre_type != Post.Canon and post_type == Post.Canon:
                self.parent.auxFormalityChanged(self, True)
            elif pre_type == Post.Canon and post_type != Post.Canon:
                self.parent.auxFormalityChanged(self, False)


    def linkChild(self, post):
        self.children.append(post)

    def linkSource(self, post):
        self.sources.append(post)


class Model:
    arrow = ">"
    separator = "|"
    empty = "_"

    def __init__(self):
        self.time_ordered = []
        self.authors = []

    def add_post(self, parent, destination, text, score=0, auxiliary=Post.Neutral, author=""):
        epoch = QDateTime.fromSecsSinceEpoch(int(time.time()))
        post = Post("X"+str(len(self.time_ordered)), parent, destination, text,
                    score=score, author=author, timestamp=epoch, auxiliary=auxiliary)
        self.time_ordered.append(post)
        return post

    def new_model(self, title, author=""):
        epoch = QDateTime.fromSecsSinceEpoch(int(time.time()))
        self.time_ordered = [Post("X0", None, None, title, author=author, timestamp=epoch)]
        if author == "":
            self.authors = []
        else:
            self.authors = [author]

    def encode_post(self, post):
        sep = self.separator
        p = post.parent.ident if post.parent is not None else self.empty
        d = post.destination.ident if post.destination is not None else self.empty
        s = str(post.score) if post.score != 0 else ""
        f = ""
        if post.auxiliary == Post.Canon:
            f = "+"
        elif post.auxiliary == Post.Suppress:
            f = "-"
        a = post.author
        t = str(post.timestamp.toSecsSinceEpoch()) if post.timestamp is not None else ""

        return p+self.arrow+post.ident+self.arrow+d+sep+post.text+sep+s+sep+f+sep+a+sep+t+sep

    def decode_post(self, line, prev_posts):
        parts = line.split(self.separator)
        idents = parts[0].split(self.arrow)
        parent = prev_posts[idents[0]] if idents[0] != self.empty else None
        destination = prev_posts[idents[2]] if idents[2] != self.empty else None
        score = 0 if parts[2] == "" else int(parts[2])
        auxiliary = Post.Neutral
        if parts[3] == "+":
            auxiliary = Post.Canon
        elif parts[3] == "-":
            auxiliary = Post.Suppress
        author = parts[4]
        timestamp = None if parts[5] == "" else QDateTime.fromSecsSinceEpoch(int(parts[5]))
        return Post(idents[1], parent, destination, parts[1],
                    score=score, auxiliary=auxiliary, author=author, timestamp=timestamp)

    def read_from_file(self, path):
        self.time_ordered = []
        self.authors = []
        curr_posts = {}
        with open(path, 'r', encoding="utf-8") as file:
            for line in file:
                new_post = self.decode_post(line, curr_posts)
                self.time_ordered.append(new_post)
                if new_post.author != "" and new_post.author not in self.authors:
                    self.authors.append(new_post.author)
                curr_posts[new_post.ident] = new_post

    def write_to_file(self, path):
        with open(path, 'w', encoding="utf-8") as file:
            for post in self.time_ordered:
                file.write(self.encode_post(post)+"\n")


class WriteBox(QWidget):
    def __init__(self, model, view):
        super(QWidget, self).__init__()

        self.model = model
        self.view = view

        v_layout = QVBoxLayout()
        self.parent_post = None
        self.destination_post = None
        self.parent_text = QLabel()
        self.destination_text = QLabel()
        self.setParent(None)
        self.setDestination(None)
        self.line_edit = QLineEdit()
        v_layout.addWidget(self.parent_text)
        v_layout.addWidget(self.line_edit)
        v_layout.addWidget(self.destination_text)
        self.setLayout(v_layout)

    def setParent(self, post):
        self.parent_post = post
        if post is None:
            self.parent_text.setText("/")
            self.parent_text.hide()
        else:
            self.parent_text.setText("/ "+post.text)
            self.parent_text.show()

    def setDestination(self, post):
        self.destination_post = post
        if post is None:
            self.destination_text.setText("\\")
            self.destination_text.hide()
        else:
            self.destination_text.setText("\\ "+post.text)
            self.destination_text.show()

    def submit(self):
        if self.line_edit.text() == "" or (self.parent_post is None and self.destination_post is None):
            return

        text = self.line_edit.text()
        auxiliary = Post.Neutral
        if text[0] == "+":
            auxiliary = Post.Canon
            text = text[1:]
        elif text[0] == "-":
            auxiliary = Post.Suppress
            text = text[1:]

        self.model.add_post(self.parent_post, self.destination_post, text, auxiliary=auxiliary,
                            author=self.view.author_select.currentText())
        self.line_edit.setText("")
        self.setParent(None)
        self.setDestination(None)
        self.view.main_doc.loadPage(self.view.main_doc.page.post)
        self.view.main_doc.setFocus()
        self.view.change_made()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Return:
            self.submit()
        elif e.key() == Qt.Key_Escape:
            self.setParent(None)
            self.setDestination(None)
        else:
            QWidget.keyPressEvent(self, e)


class VisibilitySettings(QGroupBox):
    def __init__(self):
        super(QGroupBox, self).__init__()

        #self.setTitle("Visibility Settings")
        layout = QGridLayout()

        self.show_ellipses = QCheckBox("Show ellipses")
        self.show_ellipses.setChecked(True)
        layout.addWidget(self.show_ellipses, 0, 0, 1, 2)
        self.collapse_repeats = QCheckBox("Collapse repeats")
        self.collapse_repeats.setChecked(True)
        layout.addWidget(self.collapse_repeats, 0, 2, 1, 2)
        self.separate_formality = QCheckBox("Separate formality")
        self.separate_formality.setChecked(True)
        layout.addWidget(self.separate_formality, 0, 4, 1, 2)
        layout.addWidget(QLabel("Sorting method:"), 1, 0)
        self.sorting_method = QComboBox()
        for method in LinearTree.SortingMethods:
            self.sorting_method.addItem(method)
        layout.addWidget(self.sorting_method, 1, 1)
        layout.addWidget(QLabel("Direction bias:"), 1, 2)
        self.direction_bias = QDoubleSpinBox()
        self.direction_bias.setMinimum(-1)
        self.direction_bias.setMaximum(1)
        self.direction_bias.setValue(0.5)
        self.direction_bias.setSingleStep(0.1)
        layout.addWidget(self.direction_bias, 1, 3)
        layout.addWidget(QLabel("Depth threshold:"), 1, 4)
        self.depth_threshold = QDoubleSpinBox()
        self.depth_threshold.setMinimum(0)
        self.depth_threshold.setValue(5)
        self.depth_threshold.setSingleStep(0.5)
        layout.addWidget(self.depth_threshold, 1, 5)
        self.setLayout(layout)


class LinearTree:
    Root = 0
    Child = -1
    Parent = 1
    Source = 2
    Destination = -2

    SortingMethods = {
        "best": lambda x: sorted(x, reverse=True, key=lambda c: c.score_vis),
        "worst": lambda x: sorted(x, reverse=False, key=lambda c: c.score_vis),
        "oldest": lambda x: list(x),
        "newest": lambda x: list(reversed(x)),
        "random": lambda x: random.sample(x, len(x))
    }

    def __init__(self, post, heading, kind, visibility, override=""):
        self.line_num = -1
        self.post = post
        self.heading = heading
        self.kind = kind
        self.aboves = []
        self.belows = []
        self.override = override
        self.kind = kind
        self.visibility = visibility

    def expand(self, show_ellipses, separate_formality, forward_weight, backward_weight, view_threshold, sort_method):
        new_trees = []

        above_ellipsis = False
        below_ellipsis = False

        if self.kind != LinearTree.Child and self.post.parent is not None:
            vis = self.visibility*backward_weight
            if vis >= view_threshold:
                new_tree = LinearTree(self.post.parent, self, LinearTree.Parent, vis)
                self.aboves.append(new_tree)
                new_trees.append(new_tree)
            elif show_ellipses:
                above_ellipsis = True
                self.aboves.append(LinearTree(self.post.parent, self, LinearTree.Parent, vis, override="..."))

        if self.kind != LinearTree.Source and self.post.destination is not None:
            vis = self.visibility*forward_weight
            if vis >= view_threshold:
                new_tree = LinearTree(self.post.destination, self, LinearTree.Destination, vis)
                self.belows.append(new_tree)
                new_trees.append(new_tree)
            elif show_ellipses:
                below_ellipsis = True
                self.belows.append(LinearTree(self.post.destination, self, LinearTree.Destination, vis, override="..."))

        sorted_children = LinearTree.SortingMethods[sort_method](self.post.children)
        children_patience = 1
        if separate_formality:
            sorted_children.sort(reverse=True, key=lambda x: x.formality())
        for child in sorted_children:
            if self.kind != LinearTree.Parent or child != self.heading.post:
                vis = self.visibility * forward_weight * child.score_vis
                if vis * children_patience < view_threshold:
                    if show_ellipses and not below_ellipsis:
                        self.belows.append(LinearTree(child, self, LinearTree.Child, vis, override="..."))
                    break
                new_tree = LinearTree(child, self, LinearTree.Child, vis)
                self.belows.append(new_tree)
                new_trees.append(new_tree)
                children_patience *= self.visibility

        sorted_sources = LinearTree.SortingMethods[sort_method](self.post.sources)
        sources_patience = 1
        for source in sorted_sources:
            if self.kind != LinearTree.Destination or source != self.heading.post:
                vis = self.visibility * backward_weight ** 2
                if vis * sources_patience < view_threshold:
                    if show_ellipses and not above_ellipsis:
                        self.aboves.append(LinearTree(source, self, LinearTree.Source, vis, override="..."))
                    break
                new_tree = LinearTree(source, self, LinearTree.Source, vis)
                self.aboves.append(new_tree)
                new_trees.append(new_tree)
                sources_patience *= self.visibility

        return new_trees

    def set_line_num(self, num):
        self.line_num = num

    def get_by_kind(self, kind, post):
        if kind == LinearTree.Parent:
            return self.aboves[0] if len(self.aboves) > 0 and self.aboves[0].post == post else None
        if kind == LinearTree.Destination:
            return self.belows[0] if len(self.belows) > 0 and self.belows[0].post == post else None
        if kind == LinearTree.Child:
            for x in self.belows:
                if x.post == post:
                    return x
            return None
        if kind == LinearTree.Source:
            for x in self.aboves:
                if x.post == post:
                    return x
            return None


class MainDoc(QTextEdit):

    VisAvg = 0.4
    Tab = ":     "
    DefaultFormat = QTextCharFormat()
    CanonFormat = QTextCharFormat()
    #CanonFormat.setFontUnderline(True)
    SuppressFormat = QTextCharFormat()
    #SuppressFormat.setFontStrikeOut(True)
    AboveFormat = QTextCharFormat()
    #AboveFormat.setForeground(QBrush(QColor(160, 160, 160), Qt.SolidPattern))

    def __init__(self, model, view):
        super(QTextEdit, self).__init__()

        self.setReadOnly(True)
        self.model = model
        self.view = view

        self.linear_list = []
        self.sel_line = 0

        self.back_stack = []
        self.back_pointer = 0

        self.page = None
        self.loadPage(self.model.time_ordered[0], new_doc=True)

        self.cursorPositionChanged.connect(lambda: self.setSelectLine(self.textCursor().blockNumber()))

        self.view.vis_settings.show_ellipses.stateChanged.connect(lambda: self.loadPage(self.page.post))
        self.view.vis_settings.collapse_repeats.stateChanged.connect(lambda: self.loadPage(self.page.post))
        self.view.vis_settings.separate_formality.stateChanged.connect(lambda: self.loadPage(self.page.post))
        self.view.vis_settings.direction_bias.valueChanged.connect(lambda: self.loadPage(self.page.post))
        self.view.vis_settings.depth_threshold.valueChanged.connect(lambda: self.loadPage(self.page.post))
        self.view.vis_settings.sorting_method.currentTextChanged.connect(lambda: self.loadPage(self.page.post))

        self.verticalScrollBar().valueChanged.connect(self.view.info_doc.verticalScrollBar().setValue)

    def setSelectLine(self, pos):
        self.sel_line = pos

    def loadPage(self, root, new_doc=False, add_to_stack=False):

        trace = None
        if self.page is not None and self.page.post == root and self.sel_valid():
            trace = []
            curr = self.linear_list[self.sel_line][1]
            while curr.heading is not None:
                trace.append((curr.post, curr.kind))
                curr = curr.heading

        self.setText("")

        if new_doc:
            self.back_stack = [root]
            self.back_pointer = 0
        elif add_to_stack:
            self.back_stack = self.back_stack[:self.back_pointer+1]
            self.back_stack.append(root)
            if len(self.back_stack) > 20:
                self.back_stack.pop(0)
            else:
                self.back_pointer += 1

        self.page = LinearTree(root, None, LinearTree.Root, 1)
        visibility_queue = [self.page]
        repeats_dict = {root: [self.page]}
        show_ellipses = self.view.vis_settings.show_ellipses.isChecked()
        collapse_repeats = self.view.vis_settings.collapse_repeats.isChecked()
        separate_formality = self.view.vis_settings.separate_formality.isChecked()
        forward_weight = (self.view.vis_settings.direction_bias.value() + 1) * MainDoc.VisAvg
        backward_weight = (self.view.vis_settings.direction_bias.value() - 1) * -1 * MainDoc.VisAvg
        view_threshold = MainDoc.VisAvg ** self.view.vis_settings.depth_threshold.value()
        sort_method = self.view.vis_settings.sorting_method.currentText()
        while len(visibility_queue) > 0:
            curr = visibility_queue.pop()
            extend = curr.expand(show_ellipses, separate_formality, forward_weight, backward_weight, view_threshold,
                                 sort_method)
            for e in extend:
                if collapse_repeats and e.post in repeats_dict:
                    repeats_dict[e.post].append(e)
                    if len(e.post.text) <= 30:
                        e.override = e.post.text
                    else:
                        e.override = e.post.text[:27] + "..."
                else:
                    if e.post in repeats_dict:
                        repeats_dict[e.post].append(e)
                    else:
                        repeats_dict[e.post] = [e]
                    bisect.insort_left(visibility_queue, e, key=lambda x: e.visibility)

        self.linear_list = []
        inserter = self.textCursor()
        inserter.movePosition(QTextCursor.End, QTextCursor.MoveAnchor)

        new_line = self.writeTree(self.page, inserter, 0, self.linear_list, False)

        if collapse_repeats:
            for post in repeats_dict:
                if len(repeats_dict[post]) > 1:
                    expanded_num = repeats_dict[post][0].line_num
                    for i in range(1, len(repeats_dict[post])):
                        curr_num = repeats_dict[post][i].line_num
                        diff = expanded_num - curr_num
                        suffix = "   " + ("v" if diff > 0 else "^") + str(abs(diff))
                        cursor = QTextCursor(self.document().findBlockByNumber(curr_num))
                        cursor.movePosition(QTextCursor.EndOfBlock)
                        cursor.insertText(suffix)

        self.view.info_doc.sync_text_to(self.linear_list)

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)

        if trace is None:
            self.moveSelector(new_line)
        else:
            curr = None
            next_curr = self.page
            while len(trace) > 0 and next_curr is not None:
                curr = next_curr
                step = trace.pop()
                next_curr = curr.get_by_kind(step[1], step[0])
            if next_curr is not None:
                curr = next_curr
            self.moveSelector(curr.line_num)

    def writeLine(self, inserter, linetext, tab_count, char_format=DefaultFormat):
        inserter.setCharFormat(MainDoc.DefaultFormat)
        inserter.insertText(MainDoc.Tab * tab_count)
        inserter.setCharFormat(char_format)
        inserter.insertText(linetext+"\n")
        inserter.movePosition(QTextCursor.End, QTextCursor.MoveAnchor)

    def writeTree(self, tree, inserter, tabs, linear_list, above):
        hadBelow = False
        for a in reversed(tree.aboves):
            if hadBelow or (a != tree.aboves[-1] and len(a.aboves) > 0):
                self.writeLine(inserter, "", tabs+1)
                linear_list.append(tabs+1)
            self.writeTree(a, inserter, tabs+1, linear_list, True)
            hadBelow = len(a.belows) > 0

        linetext = ""

        if tree.kind == LinearTree.Parent:
            linetext += "/ "
        elif tree.kind == LinearTree.Destination:
            linetext += "\\ "

        if tree.post.auxiliary == Post.Canon:
            linetext += "[+] "
        elif tree.post.auxiliary == Post.Suppress:
            linetext += "[-] "

        char_format = MainDoc.DefaultFormat
        formality = tree.post.formality()
        if formality == Post.Canon:
            #char_format = MainDoc.CanonFormat
            linetext += "☆ "
        elif formality == Post.Suppress:
            #char_format = MainDoc.SuppressFormat
            linetext += "🛇 "

        if tree.override != "":
            linetext += tree.override
        else:
            linetext += tree.post.text
        #linetext += "\t<"+str(tree.post.visibility())+">"
        #linetext += "\t\t\t{"+str(tree.post.canon_score)+","+str(tree.post.suppress_score)+"}"
        # if tree.kind == LinearTree.Child and tree.post.score != 0:
        #     linetext += "     *" + str(tree.post.score)



        if above:
            char_format = QTextCharFormat(char_format)
            char_format.merge(MainDoc.AboveFormat)

        self.writeLine(inserter, linetext, tabs, char_format=char_format)
        pos = len(linear_list)
        linear_list.append((tabs, tree))
        tree.set_line_num(pos)

        hadBelow = False
        for b in tree.belows:
            if hadBelow or (b != tree.belows[0] and len(b.aboves) > 0):
                self.writeLine(inserter, "", tabs+1)
                linear_list.append(tabs+1)
            self.writeTree(b, inserter, tabs+1, linear_list, above)
            hadBelow = len(b.belows) > 0

        return pos

    def sel_valid(self):
        return self.sel_line < len(self.linear_list) and not isinstance(self.linear_list[self.sel_line], int)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Up:
            if e.modifiers() & Qt.ShiftModifier and self.sel_valid():
                line = self.searchForLines(self.sel_line, -1, self.linear_list[self.sel_line][0], True)
                self.moveSelector(line)
            elif self.sel_line > 0:
                line = self.sel_line - 1
                while isinstance(self.linear_list[line], int):
                    line -= 1
                self.moveSelector(line)
        elif e.key() == Qt.Key_Down:
            if e.modifiers() & Qt.ShiftModifier and self.sel_valid():
                line = self.searchForLines(self.sel_line, 1, self.linear_list[self.sel_line][0], True)
                self.moveSelector(line)
            elif self.sel_line < len(self.linear_list) - 1:
                line = self.sel_line + 1
                while isinstance(self.linear_list[line], int):
                    line += 1
                self.moveSelector(line)
        elif e.key() == Qt.Key_Left:
            if not self.sel_valid():
                return
            kind = self.linear_list[self.sel_line][1].kind
            if kind == LinearTree.Parent or kind == LinearTree.Source:
                line = self.searchForLines(self.sel_line, 1, self.linear_list[self.sel_line][0] - 1, False)
                if line >= 0:
                    self.moveSelector(line)
            elif kind == LinearTree.Destination or kind == LinearTree.Child:
                line = self.searchForLines(self.sel_line, -1, self.linear_list[self.sel_line][0] - 1, False)
                if line >= 0:
                    self.moveSelector(line)
        elif e.key() == Qt.Key_Right:
            if not self.sel_valid():
                return
            if e.modifiers() & Qt.ShiftModifier:
                line = self.searchForLines(self.sel_line, -1, self.linear_list[self.sel_line][0] + 1, False)
                if line >= 0:
                    self.moveSelector(line)
            else:
                line = self.searchForLines(self.sel_line, 1, self.linear_list[self.sel_line][0] + 1, False)
                if line >= 0:
                    self.moveSelector(line)
        elif e.key() == Qt.Key_Space:
            if not self.sel_valid():
                return
            add_stack = self.page.post != self.linear_list[self.sel_line][1].post
            self.loadPage(self.linear_list[self.sel_line][1].post, add_to_stack=add_stack)
        elif e.key() == Qt.Key_Return:
            if not self.sel_valid():
                return
            if e.modifiers() & Qt.ShiftModifier:
                if self.view.write_box.destination_post != self.linear_list[self.sel_line][1].post:
                    self.view.write_box.setDestination(self.linear_list[self.sel_line][1].post)
                else:
                    self.view.write_box.line_edit.setFocus()
            else:
                if self.view.write_box.parent_post != self.linear_list[self.sel_line][1].post:
                    self.view.write_box.setParent(self.linear_list[self.sel_line][1].post)
                else:
                    self.view.write_box.line_edit.setFocus()
        elif e.key() == Qt.Key_Escape:
            self.view.write_box.setParent(None)
            self.view.write_box.setDestination(None)
        elif e.key() == Qt.Key_Backspace:
            if len(self.back_stack) > 1:
                if e.modifiers() & Qt.ShiftModifier:
                    if self.back_pointer < len(self.back_stack) - 1:
                        self.back_pointer += 1
                        self.loadPage(self.back_stack[self.back_pointer])
                else:
                    if self.back_pointer > 0:
                        self.back_pointer -= 1
                        self.loadPage(self.back_stack[self.back_pointer])
        elif e.key() == Qt.Key_Plus or e.key() == Qt.Key_Equal:
            if self.sel_valid() and self.linear_list[self.sel_line][1].kind == LinearTree.Child:
                self.linear_list[self.sel_line][1].post.addScore(1)
                self.loadPage(self.page.post)
                self.view.change_made()
        elif e.key() == Qt.Key_Minus:
            if self.sel_valid() and self.linear_list[self.sel_line][1].kind == LinearTree.Child:
                self.linear_list[self.sel_line][1].post.addScore(-1)
                self.loadPage(self.page.post)
                self.view.change_made()
        else:
            QTextEdit.keyPressEvent(self, e)

    def searchForLines(self, start_line, step, tabs, settle_for_end):
        new_line = start_line + step
        while 0 <= new_line < len(self.linear_list) and (isinstance(self.linear_list[new_line], int) or
                                                         self.linear_list[new_line][0] >= tabs):
            if not isinstance(self.linear_list[new_line], int) and self.linear_list[new_line][0] == tabs:
                return new_line
            new_line += step
        if settle_for_end:
            if new_line >= len(self.linear_list):
                new_line = len(self.linear_list) - 1
            elif new_line < 0:
                new_line = 0
            return new_line
        return -1

    def moveSelector(self, new_line):
        cursor = self.textCursor()
        # cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
        cursor.movePosition(QTextCursor.PreviousBlock, QTextCursor.MoveAnchor, n=self.textCursor().blockNumber() - new_line)
        cursor.movePosition(QTextCursor.NextBlock, QTextCursor.MoveAnchor, n=new_line - self.textCursor().blockNumber())
        cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)

        self.setTextCursor(cursor)


class InfoDoc(QTextEdit):
    def __init__(self):
        super(QTextEdit, self).__init__()

        self.setReadOnly(True)
        self.horizontalScrollBar().setEnabled(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.verticalScrollBar().setEnabled(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedWidth(120)
        self.setLineWrapMode(QTextEdit.NoWrap)
        self.setEnabled(False)

    def sync_text_to(self, lines):
        self.setText("")
        for i, l in enumerate(lines):
            line = " "
            if not isinstance(l, int):
                tree = l[1]
                line += tree.post.author
                if tree.post.timestamp is not None:
                    if line != " ":
                        line += ", "

                    curr_time = QDateTime.currentDateTime()
                    last_time = tree.post.timestamp
                    if curr_time.date().year() == last_time.date().year():
                        if curr_time.date().month() == last_time.date().month() and \
                           curr_time.date().day() == last_time.date().day():
                            line += last_time.toString("hh:mm")
                        else:
                            line += last_time.toString("MM/dd")
                    else:
                        line += last_time.toString("MM/yyyy")

                if tree.kind == LinearTree.Child and tree.post.score != 0:
                    line += " | " + str(tree.post.score)

            self.append(line)
        self.append("\n")

    def keyPressEvent(self, e):
        if e.key() != Qt.Key_Up and e.key() != Qt.Key_Down and e.key() != Qt.Key_PageUp and e.key() != Qt.Key_PageDown\
                and e.key() != Qt.Key_Space:
            QTextEdit.keyPressEvent(self, e)


class App(QApplication):

    def __init__(self, argv):
        super(QApplication, self).__init__(argv)

        self.setWindowIcon(QIcon("C:/Users/pavan/PycharmProjects/BrainstormerPrototype/bug.ico"))
        if len(sys.argv) > 1:
            self.view = View(sys.argv[1])
        else:
            self.view = View()
        self.view.show()


if __name__ == '__main__':
    app = App(sys.argv)
    sys.exit(app.exec_())
