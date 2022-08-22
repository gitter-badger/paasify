

class PaasifyError(Exception):
    """Base class for other exceptions"""

    paasify = True
    rc = 1
    
    def __init__(self, message, rc=None, advice=None):
        #self.paasify = True
        self.advice = advice
        self.rc = rc or self.rc
        super().__init__(message)

class ProjectNotFound(PaasifyError):
    """Raised when project is not found"""
    rc = 17

class ProjectInvalidConfig(PaasifyError):
    """Raised when project config contains errors"""
    rc = 18

class ShellCommandFailed(PaasifyError):
    """Raised when project config contains errors"""
    rc = 18

class StackNotFound(PaasifyError):
    """Raised when stack is not found"""
    rc = 19

class StackMissingOrigin(PaasifyError):
    """Raised when a stack origin is not determined"""
    rc = 20

class DockerBuildConfig(PaasifyError):
    "Raised when docker-config failed"
    rc = 30

class DockerCommandFailed(PaasifyError):
    "Raised when docker-config failed"
    rc = 32

class JsonnetBuildTag(PaasifyError):
    "Raised when jsonnet failed"
    rc = 31

class DockerUnsupportedVersion(PaasifyError):
    "Raised when docker-config failed"
    rc = 33

class JsonnetProcessError(PaasifyError):
    "Raised when jsonnet file can't be executed"
    rc = 34

class PaasifyNestedProject(PaasifyError):
    "Raised when a project is created into an existing project"
    rc = 35