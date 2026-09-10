import * as monaco from 'monaco-editor/esm/vs/editor/editor.api';
import 'monaco-editor/esm/vs/basic-languages/python/python.contribution';
import 'monaco-editor/esm/vs/basic-languages/java/java.contribution';
import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution';
import 'monaco-editor/esm/vs/language/typescript/monaco.contribution';
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
import TypeScriptWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker?worker';

// Bundle workers locally; never load the editor from a CDN.
self.MonacoEnvironment = {
  getWorker(_, label) {
    return ['javascript', 'typescript'].includes(label) ? new TypeScriptWorker() : new EditorWorker();
  },
};
monaco.editor.defineTheme('interviv-code', {
  base: 'vs-dark', inherit: true, rules: [],
  colors: { 'editor.background': '#17191d', 'editor.lineHighlightBackground': '#202329', 'editorCursor.foreground': '#a3e635' },
});
export { monaco };
