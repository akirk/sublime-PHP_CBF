import os
import sublime
import sublime_plugin
import subprocess
import difflib

"""
Set some constants
"""
SETTINGS_FILE = 'PHP_CBF.sublime-settings'

"""
GET/SET SETTINGS CLASS FROM SUBLIME-PHPCS
THANKS AND CREDITS TO: Ben Selby (github: @BENMATSELBY)
"""
class Preferences:
    def load(self):
        self.settings = sublime.load_settings(SETTINGS_FILE)

    def get(self, key):
        if sublime.active_window() is not None and sublime.active_window().active_view() is not None:
          conf = sublime.active_window().active_view().settings().get('PHP_CBF')
          if conf is not None and key in conf:
            return conf.get(key)

        return self.settings.get(key)

"""
CHECK SUBLIME VERSION
LOAD SETTINGS
"""
settings = Preferences()

def plugin_loaded():
    settings.load()

"""
MAIN PHP_CODESNIFFER CLASS
HANDLE THE REQUESTS FROM SUBLIME
"""
class PHP_CBF:
  # Type of the view, phpcs or phpcbf.
  file_view   = None
  window      = None
  processed   = False
  process_anim_idx = 0
  process_anim = {
    'windows': ['|', '/', '-', '\\'],
    'linux': ['|', '/', '-', '\\'],
    'osx': [u'\u25d0', u'\u25d3', u'\u25d1', u'\u25d2']
  }
  regions = []

  def run(self, window , msg):
    self.window = window
    content = window.active_view().substr(sublime.Region(0, window.active_view().size()))

    args = self.get_command_args('phplint')
    file_path = window.active_view().file_name()

    shell = False
    if os.name == 'nt':
      shell = True

    proc = subprocess.Popen(args, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

    stdout, stderr = proc.communicate(input=content.encode('utf-8'))
    data = stdout.decode('utf-8')

    if proc.returncode != 0:
      print('Invalid PHP');
      self.window.status_message('Invalid PHP');
      return

    args = self.get_command_args('phpcbf')
    proc = subprocess.Popen(args, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

    if file_path:
      source = 'phpcs_input_file: ' + file_path + "\n" + content;
    else:
      source = content;

    stdout, stderr = proc.communicate(input=source.encode('utf-8'))
    data = stdout.decode('utf-8')

    if proc.returncode > 2:
      self.window.status_message('Error ' + data);
      return

    if proc.returncode == 0:
      print('All good, nothing to fix');
      return

    self.process_phpcbf_results(data, window, content)

  def process_phpcbf_results(self, fixed_content, window, content):
    # Remove the gutter markers.
    self.window    = window
    self.file_view = window.active_view()

    # If the length is way off there must have been an error
    if len(fixed_content) * 1.2 < len(content):
      self.window.status_message('Error');
      return

    # Get the diff between content and the fixed content.
    difftxt = self.run_diff(window, content, fixed_content)
    self.processed = True

    if not difftxt:
      return

    # Show diff text in the results panel.
    self.window.status_message('');

    self.file_view.run_command('set_view_content', {'data':fixed_content, 'replace':True})

  def run_diff(self, window, origContent, fixed_content):
    try:
        a = origContent.splitlines()
        b = fixed_content.splitlines()
    except UnicodeDecodeError as e:
        self.window.status_message("Diff only works with UTF-8 files")
        return

    # Get the diff between original content and the fixed content.
    diff = difflib.unified_diff(a, b, 'Original', 'Fixed', lineterm='')
    difftxt = u"\n".join(line for line in diff)

    if difftxt == "":
      self.window.status_message('')
      return

    return difftxt

  def get_command_args(self, cmd_type):
    args = []

    if settings.get('php_path'):
      args.append(settings.get('php_path'))
    elif os.name == 'nt':
      args.append('php')

    if cmd_type == 'phpcbf':
      args.append(settings.get('phpcbf_path'))

    standard_setting = settings.get('phpcs_standard')
    standard = ''

    if type(standard_setting) is dict:
      for folder in self.window.folders():
        folder_name = os.path.basename(folder)
        if folder_name in standard_setting:
          standard = standard_setting[folder_name]
          break

      if standard == '' and '_default' in standard_setting:
        standard = standard_setting['_default']
    else:
      standard = standard_setting

    if cmd_type == 'phpcbf':
      if settings.get('phpcs_standard'):
        args.append('--standard=' + standard)
      else:
        args.append('--standard=${folder}/phpcs.xml')

      args.append('-')

    if cmd_type == 'phplint':
      args.append('-l')

    if settings.get('additional_args'):
      args += settings.get('additional_args')

    return args

# Init PHPCBF.
phpcbf = PHP_CBF()

"""
START SUBLIME TEXT
COMMANDS AND EVENTS
"""
class set_view_content(sublime_plugin.TextCommand):
    def run(self, edit, data, replace=False):
      if replace == True:
        self.view.replace(edit, sublime.Region(0, self.view.size()), data)
      else:
        self.view.insert(edit, 0, data)

class PhpcbfCommand(sublime_plugin.WindowCommand):
  def run(self):
    phpcbf.run(self.window, 'Running PHPCS Fixer  ')

class PhpcbfEventListener(sublime_plugin.EventListener):
  def on_pre_save(self, view):
    self.filename = os.path.basename(view.file_name())
    if (
        self.filename.endswith('.php') == True and
        self.filename.startswith('.') == False and
        settings.get('fix_on_save') == True
      ):
        sublime.active_window().run_command("phpcbf")
        return
