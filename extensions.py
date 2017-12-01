import lldb
import os.path
import re
import uuid


def __lldb_init_module(debugger, python_context):
    module_name = __name__

    debugger.HandleCommand(
        'command script add -f %s.PrintJSONForDictionary jsonPrint' % module_name)
    debugger.HandleCommand(
        'command script add -c %s.SaveImageToDesktop saveImage' % module_name)


def PrintJSONForDictionary(debugger, command, execution_context, output, python_context):
    # Get language for compile unit (file)
    language = execution_context.frame.compile_unit.GetLanguage()

    dictionaryExpression = None

    # If language is Swift, use expression straightaway
    # otherwise get address for object
    if language == lldb.eLanguageTypeSwift:
        dictionaryExpression = command
    else:
        inputValueAddress = evaluateInCurrentContext(command).value
        dictionaryExpression = "unsafeBitCast(%s, to: NSDictionary.self)" % inputValueAddress

    stringFromDict = """
    import Foundation
    let options = JSONSerialization.WritingOptions.init(rawValue: 1)
    let jsonData = JSONSerialization.data(withJSONObject: %s, options: options)
    String(data: jsonData, encoding: String.Encoding.utf8)!
    """ % (dictionaryExpression)

    # Evaluate dictionary result
    result = evaluateInSwiftContext(stringFromDict).description
    # Remove leading and trailing quote
    result = re.findall(r'^\"(.+)\"$', result, re.MULTILINE)[0]
    # Unescape quotes
    resultUnescaped = result.replace('\\\"', '"').replace('\\n', '\n')

    print >>output, resultUnescaped


class SaveImageToDesktop:
    def __init__(self, debugger, python_context):
        print 'The "%s" from %s is loaded' % (self.__class__.__name__, __file__)

    def __call__(self, debugger, command, execution_context, output):
        # Get address of the result of evaluating expression
        inputValueAddress = evaluateInCurrentContext(command).value

        # Store image as file in /tmp folder
        saveImageToTmp = """
        import Foundation
        let image = unsafeBitCast(%s, to: UIImage.self)
        let imageData = UIImagePNGRepresentation(image)
        let path = NSTemporaryDirectory().appending("img_tmp.png")
        try! imageData.write(to: URL(fileURLWithPath: path))
        path
        """ % (inputValueAddress)

        # Set src and destination paths
        fromPath = evaluateInSwiftContext(saveImageToTmp).summary
        pathToSave = "~/Desktop/lldb_stored_images/lldb_%s.png" % uuid.uuid4()
        toPath = os.path.expanduser(pathToSave)

        debugger.HandleCommand("platform get-file %s %s" % (fromPath, toPath))

    def get_short_help(self):
        return "Store UIImage to ~/Desktop/lldb_stored_images/ with random name"

    def get_long_help(self):
        return "saveImage <UIImageVariableOrAddress> \nCommand loaded from %s" % __file__


def evaluateInCurrentContext(expr):
    # expression -- <expr>
    return _evaluateInContext(expr)


def evaluateInObjcContext(expr):
    # expression -l objc -- <expr>
    return _evaluateInContext(expr, lldb.eLanguageTypeObjC)


def evaluateInSwiftContext(expr):
    # expression -l swift -- <expr>
    return _evaluateInContext(expr, lldb.eLanguageTypeSwift)


def _evaluateInContext(expr, language=None):
    options = lldb.SBExpressionOptions()
    if language != None:
        options.SetLanguage(language)

    target = lldb.debugger.GetSelectedTarget()
    currentFrame = target.GetProcess().GetSelectedThread().GetSelectedFrame()
    value = currentFrame.EvaluateExpression(expr, options)  # SBValue
    error = value.error
    if error.Fail():
        print error
    return value
