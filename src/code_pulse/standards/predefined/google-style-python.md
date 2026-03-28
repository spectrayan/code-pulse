# Google Python Style Guide (Summary)

Key conventions from Google's Python style guide.

## Imports
Use `import` for packages and modules only. Use `from x import y` where y is a module. Avoid wildcard imports.

## Naming
- `module_name`, `package_name`, `ClassName`, `method_name`, `function_name`
- `GLOBAL_CONSTANT_NAME`, `instance_var_name`, `_private_name`

## Formatting
- 4-space indentation, no tabs
- Maximum line length: 80 characters
- Use parentheses for line continuation

## Docstrings
Use Google-style docstrings with Args, Returns, and Raises sections. All public modules, classes, and functions require docstrings.

## Type Annotations
Use type annotations for function signatures. Prefer `Optional[X]` over `X | None` for Python 3.9 compatibility.

## Best Practices
Avoid mutable default arguments. Use `is` for None comparisons. Prefer list comprehensions over map/filter.
