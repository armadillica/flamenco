"""RNA Overrides for Blender Render jobs.

Setting RNA overrides is done by PATCHing the job. The actual insertion of
RNA overrides into new/existing jobs is done by the job compiler.
"""
import ast
import typing


def validate_rna_overrides(rna_overrides: typing.List[str]) \
        -> typing.Optional[typing.Tuple[str, int]]:
    """Check that the RNA overrides are valid Python.

    The code may still raise exceptions when run (for example when accesing
    bpy.scene instead of bpy.context.scene), but at least the syntax should
    be valid.

    :returns: A tuple (error message, line number) on error or None when
        validation passes. The line number can be 0 to indicate 'unknown'.
    """

    all_py = '\n'.join(rna_overrides)

    try:
        ast.parse(all_py, 'rna-overrides')
    except SyntaxError as ex:
        msg, info = ex.args
        file, line_num, char_num, line = info
        return f'{msg} in line {line.strip()!r}', line_num
    except ValueError as ex:
        return str(ex), 0

    return None
