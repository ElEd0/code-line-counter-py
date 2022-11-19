from PyQt5 import uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QApplication, QErrorMessage, QMainWindow,
		QTreeWidgetItem, QFileDialog)

import sys, os, json
		
class MainWindow(QMainWindow):
	
	VERSION = "1.0"
	
	def __init__(self):
		super(MainWindow, self).__init__()
		
		uic.loadUi("main.ui", self)
		
		self.currProject = None
		self.treeIsDirty = True
		self.resultDirs = 0
		self.resultFiles = 0
		self.resultLines = 0
		self.resultChars = 0
	
		self.openButton.clicked.connect(self.open)
		self.saveButton.clicked.connect(lambda: self.save(self.currProject == None))
		self.saveAsButton.clicked.connect(lambda: self.save(True))
		self.browsePathButton.clicked.connect(self.browsePath)
		self.searchButton.clicked.connect(lambda: self.search())
		self.startButton.clicked.connect(self.start)
		
		self.projectPath.textChanged.connect(self.updateButtons)
		self.projectExtensions.textChanged.connect(self.updateButtons)
		self.projectIgnoreFiles.textChanged.connect(self.updateButtons)
		
		self.projectCountCharacters.stateChanged.connect(lambda: self.projectStripLines.setEnabled(self.projectCountCharacters.isChecked()))
	
		self.setWindowTitle(self.getProgramName())
		self.setWindowIcon(QIcon(os.path.dirname(os.path.realpath(__file__)) + "/icon.png"))
		
		
	def getProgramName(self):
		return "Code Line Counter V" + self.VERSION
	
	def updateButtons(self):
		path = self.projectPath.text().strip()
		extensions = self.projectExtensions.text().strip()
		
		enabled = path != "" and extensions != ""
		
		self.saveButton.setEnabled(enabled)
		self.saveAsButton.setEnabled(enabled)
		self.searchButton.setEnabled(enabled)
		self.startButton.setEnabled(enabled)
		
		self.treeIsDirty = True
	
	def updateResults(self):
		self.directoryCount.setText(str(self.resultDirs))
		self.fileCount.setText(str(self.resultFiles))
		self.lineCount.setText(str(self.resultLines))
		self.characterCount.setText(str(self.resultChars))
	
	def open(self):
		projPath, _ = QFileDialog.getOpenFileName(self, 'Open Project', None, "Text files (*.clc)")
		if projPath:
			try:
				with open(projPath, "r") as f:
					data = json.loads(f.read())
					self.projectPath.setText(data['path'])
					self.projectExtensions.setText(data['extensions'])
					self.projectIgnoreFiles.setText(data['ignoreFiles'])
					self.projectCountEmpty.setChecked(data['countEmpty'])
					self.projectCountCharacters.setChecked(data['countCharacters'])
					self.projectStripLines.setChecked(data['stripLines'])
					
					self.updateButtons()

					unselectedFiles = data['unselectedFiles'] if 'unselectedFiles' in data else []
					self.search(unselectedFiles)
					
					self.currProject = projPath
					self.setWindowTitle(self.getProgramName() + " - " + os.path.basename(self.currProject))
			except Exception as e:
				errorDialog = QErrorMessage()
				errorDialog.showMessage("Error opening project " + projPath + ": " + str(e))
				errorDialog.exec_()
				
	
	def save(self, asNew=False):
		data = {
			'path': self.projectPath.text(),
			'extensions': self.projectExtensions.text(),
			'ignoreFiles': self.projectIgnoreFiles.text(),
			'countEmpty': self.projectCountEmpty.isChecked(),
			'countCharacters': self.projectCountCharacters.isChecked(),
			'stripLines': self.projectStripLines.isChecked()
		}
		
		rootNode = self.projectTree.topLevelItem(0)
		if rootNode != None:
			data['unselectedFiles'] = self.getUnselectedFilesRecursive(rootNode, rootNode.text(0))
		if asNew or self.currProject == None:
			self.currProject, _ = QFileDialog.getSaveFileName(self, 'Save Project File')
		
		if self.currProject:
			sp = os.path.splitext(self.currProject)
			self.currProject = sp[0] + ".clc"
			with open(self.currProject, "w") as f:
				f.write(json.dumps(data, indent=4))
				f.close()
				self.setWindowTitle(self.getProgramName() + " - " + os.path.basename(self.currProject))
	
	def getUnselectedFilesRecursive(self, parentNode, parentPath):
		files = []
		if parentNode.checkState(0) == Qt.Unchecked:
			return [ parentPath ]
		childCount = parentNode.childCount()
		if childCount != 0:
			for i in range(childCount):
				node = parentNode.child(i)
				nodePath = parentPath + "/" + node.text(0)
				if node.checkState(0) == Qt.Unchecked:
					files += [ nodePath ]
					continue
				files += self.getUnselectedFilesRecursive(node, nodePath)
		return files


	
	def browsePath(self):
		path = str(QFileDialog.getExistingDirectory(self, "Select Project directory"))
		if path: self.projectPath.setText(path)
		
	def search(self, unselectedFiles = []):
		self.treeIsDirty = True
		self.searchButton.setText("Searching")
		self.searchButton.setEnabled(False)
		
		path = self.projectPath.text().strip()
		if not os.path.isdir(path):
			errorDialog = QErrorMessage()
			errorDialog.showMessage("Directory " + path + " does not exist!")
			errorDialog.exec_()
			return False
		self.extensions = []
		extensions = self.projectExtensions.text().strip().split(" ")
		for ext in extensions:
			ext = ext.strip()
			if ext[0] == ".": ext = ext[1:]
			if ext != "" and ext not in self.extensions:
				self.extensions.append(ext)
		self.ignoreFiles = []
		ignoreFiles = self.projectIgnoreFiles.text().strip().split(" ")
		for file in ignoreFiles:
			file = file.strip()
			if file != "" and file not in self.ignoreFiles:
				self.ignoreFiles.append(file)
		
		self.projectTree.clear()
		rootItem = QTreeWidgetItem(self.projectTree)
		rootItem.setText(0, path)
		rootItem.setFlags(rootItem.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
		rootItem.setCheckState(0, Qt.Checked)
		
		self.recursiveSearch(path, rootItem, unselectedFiles)
		
		rootItem.setExpanded(True)
		
		self.searchButton.setText("Search")
		self.searchButton.setEnabled(True)
		self.treeIsDirty = False
		return True
		
		
	def recursiveSearch(self, parentDir, parentNode, unselectedFiles, overrideSelected=False):
		files = []
		for file in os.listdir(parentDir):
			if file in self.ignoreFiles:
				continue
			path = os.path.join(parentDir, file)
			if os.path.isfile(path):
				sp = os.path.splitext(file)
				ext = sp[1][1:]
				if ext in self.extensions:
					files.append(path)
					node = QTreeWidgetItem(parentNode)
					node.setText(0, file)
					node.setFlags(node.flags() | Qt.ItemIsUserCheckable)
					node.setCheckState(0, Qt.Unchecked if overrideSelected or path in unselectedFiles else Qt.Checked)
			elif os.path.isdir(path):
				node = QTreeWidgetItem(parentNode)
				node.setText(0, file)
				node.setFlags(node.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
				unselected = overrideSelected or path in unselectedFiles
				node.setCheckState(0, Qt.Unchecked if unselected else Qt.Checked)
				nextFiles = self.recursiveSearch(path, node, unselectedFiles, unselected)
				if len(nextFiles) != 0:
					files.append(nextFiles)
				else:
					parentNode.removeChild(node)
				
		return files
	
	def setProgress(self, value):
		self.progress.setValue(value)
		self.updateResults()
		
	def setResultDirs(self, val):
		self.resultDirs = val
		
	def setResultFiles(self, val):
		self.resultFiles = val
		
	def setResultLines(self, val):
		self.resultLines = val
		
	def setResultChars(self, val):
		self.resultChars = val
	
	def start(self):
		rootItem = self.projectTree.topLevelItem(0)
		if rootItem == None or self.treeIsDirty:
			if not self.search():
				return
		self.countThread = CountThread(rootItem, 
									   self.projectCountEmpty.isChecked(),
									   self.projectCountCharacters.isChecked(),
									   self.projectStripLines.isChecked())
		self.countThread.progress.connect(lambda value: self.setProgress(value))
		self.countThread.directories.connect(lambda value: self.setResultDirs(value))
		self.countThread.files.connect(lambda value: self.setResultFiles(value))
		self.countThread.lines.connect(lambda value: self.setResultLines(value))
		self.countThread.characters.connect(lambda value: self.setResultChars(value))
		self.countThread.errorSignal.connect(lambda error: print(error))
		
		self.countThread.start()
		self.progress.show()
		

class CountThread(QThread):
	progress = pyqtSignal("int")
	directories = pyqtSignal("int")
	files = pyqtSignal("int")
	lines = pyqtSignal("int")
	characters = pyqtSignal("int")
	text = pyqtSignal("QString")
	errorSignal = pyqtSignal(str)

	def __init__(self, rootNode, countEmptyLines, countCharacters, stripLines) -> None:
		QThread.__init__(self)
		self.rootNode = rootNode
		self.countEmptyLines = countEmptyLines
		self.countCharacters = countCharacters
		self.stripLines = stripLines
		self.dirCount = 0
		self.fileCount = 0
		self.lineCount = 0
		self.charCount = 0

	def run(self) -> None:
		try:
			
			files = self.getFilesRecursive(self.rootNode, self.rootNode.text(0))
			self.fileCount = len(files)
			
			self.directories.emit(self.dirCount)
			self.files.emit(self.fileCount)
			self.progress.emit(0)
			
			lastProgress = 0
			f = 0
			for file in files:
				fh = open(file, "r")
				lines = fh.readlines()
				
				if self.countCharacters:
					for line in lines:
						lineStrip = line.strip()
						if self.countEmptyLines or lineStrip != "":
							self.lineCount += 1
							self.charCount += len(lineStrip) if self.stripLines else len(line)
				else:
					if self.countEmptyLines:
						self.lineCount += len(lines)
					else:
						for line in lines:
							if line.strip() == "":
								continue
							self.lineCount += 1
				
				currProgress = int((f * 100) / self.fileCount)
				if currProgress != lastProgress:
					lastProgress = currProgress
					self.lines.emit(self.lineCount)
					self.characters.emit(self.charCount)
					self.progress.emit(currProgress)
				f += 1
				
			self.lines.emit(self.lineCount)
			self.characters.emit(self.charCount)
			self.progress.emit(100)
				
			
		except Exception as e:
			self.errorSignal.emit(str(e))

	def getFilesRecursive(self, parentNode, parentPath):
		files = []
		if parentNode.checkState(0) == Qt.Unchecked:
			return files
		childCount = parentNode.childCount()
		if childCount == 0:
			files = [ parentPath ]
		else:
			self.dirCount += 1
			for i in range(childCount):
				node = parentNode.child(i)
				if node.checkState(0) == Qt.Unchecked:
					continue
				files += self.getFilesRecursive(node, parentPath + "/" + node.text(0))
		return files

			
if __name__ == '__main__':
	app = QApplication([])
	
	mainWindow = MainWindow()
	mainWindow.show()
	
	sys.exit(app.exec_())

