from pydantic import ValidationError


class SafeValidationError(Exception):
    def __init__(self, error: ValidationError):
        errors = error.errors(include_input=False, include_url=False)
        super().__init__(f"Invalid model: {error.title}: {errors}")
