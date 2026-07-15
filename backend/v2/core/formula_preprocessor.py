"""Convert mathematical notation to natural language for better embedding.

Mathematical formulas don't embed well because tokenizers break them into
individual characters. This module converts common math patterns to
natural language descriptions that embedding models can understand.
"""

from __future__ import annotations

import re


def formula_to_natural_language(query: str) -> str:
    """Convert mathematical notation in a query to natural language.

    This preprocessing step helps embedding models understand math queries
    by converting symbolic notation to descriptive text.

    Examples:
        "∆ = a11 A21 + a12 A22" → "determinant expansion using cofactors"
        "A = [1 2; 3 4]" → "2x2 matrix"
        "∫ x^2 dx" → "integral of x squared"
        "H2O + NaOH" → "reaction between water and sodium hydroxide"
    """
    result = query

    # Apply transformations in order
    result = _convert_determinant_notation(result)
    result = _convert_matrix_notation(result)
    result = _convert_calculus_notation(result)
    result = _convert_chemistry_notation(result)
    result = _convert_physics_formulas(result)
    result = _convert_common_symbols(result)

    return result


def _convert_determinant_notation(text: str) -> str:
    """Convert determinant and cofactor notation to natural language."""
    # Pattern: ∆ = a11 A21 + a12 A22 + ...
    if re.search(r'[∆δ]\s*=\s*a\s*\d+\s*A\s*\d+', text):
        return "determinant expansion using cofactors"

    # Pattern: a11 A21 + a12 A22 = 0
    if re.search(r'a\s*\d+\s*A\s*\d+.*=\s*0', text):
        return "cofactor expansion formula for determinant"

    # Pattern: |A| or det(A)
    if re.search(r'\|A\|', text) or re.search(r'det\s*\(', text):
        return "determinant of a matrix"

    # Pattern: A_ij (cofactor notation)
    if re.search(r'A\s*\d+\s*\d+', text) and ('cofactor' in text.lower() or 'minor' in text.lower()):
        return "matrix cofactors and minors"

    return text


def _convert_matrix_notation(text: str) -> str:
    """Convert matrix notation to natural language."""
    # Pattern: [1 2; 3 4] or [1 2 3; 4 5 6; 7 8 9]
    matrix_match = re.search(r'\[[\d\s,;.\-]+\]', text)
    if matrix_match:
        matrix_str = matrix_match.group()
        rows = matrix_str.strip('[]').split(';')
        n_rows = len(rows)
        n_cols = len(rows[0].split()) if rows else 0
        return f"{n_rows}x{n_cols} matrix"

    # Pattern: A = [ or B = [
    if re.search(r'[A-Z]\s*=\s*\[', text):
        return "matrix"

    # Pattern: row matrix, column matrix, square matrix
    if 'row matrix' in text.lower():
        return "row matrix definition"
    if 'column matrix' in text.lower():
        return "column matrix definition"
    if 'square matrix' in text.lower():
        return "square matrix definition"

    # Pattern: matrix multiplication
    if re.search(r'multiply.*matrix', text.lower()) or re.search(r'matrix.*multiplication', text.lower()):
        return "matrix multiplication"

    # Pattern: matrix addition
    if re.search(r'add.*matrix', text.lower()) or re.search(r'matrix.*addition', text.lower()):
        return "matrix addition"

    # Pattern: inverse matrix
    if re.search(r'inverse.*matrix', text.lower()) or re.search(r'matrix.*inverse', text.lower()):
        return "matrix inverse"

    # Pattern: transpose
    if 'transpose' in text.lower():
        return "matrix transpose"

    return text


def _convert_calculus_notation(text: str) -> str:
    """Convert calculus notation to natural language."""
    # Pattern: ∫ f(x) dx
    if re.search(r'∫.*dx', text):
        return "integration"

    # Pattern: d/dx f(x)
    if re.search(r'd/dx', text):
        return "differentiation"

    # Pattern: ∂f/∂x
    if re.search(r'∂.*∂', text):
        return "partial differentiation"

    # Pattern: lim x→∞
    if re.search(r'lim.*→', text):
        return "limit"

    # Pattern: ∑ from i=1 to n
    if re.search(r'∑|\\sum', text):
        return "summation"

    # Pattern: x^2, x^n, x^{n+1}
    if re.search(r'x\^', text):
        return "polynomial"

    return text


def _convert_chemistry_notation(text: str) -> str:
    """Convert chemical notation to natural language."""
    # Common chemical formulas
    chem_formulas = {
        'H2O': 'water',
        'CO2': 'carbon dioxide',
        'NaCl': 'sodium chloride',
        'NaOH': 'sodium hydroxide',
        'HCl': 'hydrochloric acid',
        'H2SO4': 'sulfuric acid',
        'Na2CO3': 'sodium carbonate',
        'CaCO3': 'calcium carbonate',
        'Fe2O3': 'iron oxide',
        'CH4': 'methane',
        'C2H5OH': 'ethanol',
        'NH3': 'ammonia',
        'O2': 'oxygen',
        'N2': 'nitrogen',
        'H2': 'hydrogen',
    }

    result = text
    for formula, name in chem_formulas.items():
        if formula in text:
            result = result.replace(formula, name)

    # Pattern: → (reaction arrow)
    if '→' in result or '->' in result:
        result = result.replace('→', ' produces ').replace('->', ' produces ')

    # Pattern: ⇌ (equilibrium)
    if '⇌' in result:
        result = result.replace('⇌', ' is in equilibrium with ')

    # Pattern: ↑ (gas evolution)
    if '↑' in result:
        result = result.replace('↑', ' gas')

    # Pattern: ↓ (precipitate)
    if '↓' in result:
        result = result.replace('↓', ' precipitate')

    return result


def _convert_physics_formulas(text: str) -> str:
    """Convert common physics formulas to natural language."""
    physics_formulas = {
        'F = ma': "Newton's second law",
        'F=ma': "Newton's second law",
        'E = mc^2': "mass-energy equivalence",
        'E=mc^2': "mass-energy equivalence",
        'V = IR': "Ohm's law",
        'V=IR': "Ohm's law",
        'P = IV': "electrical power",
        'P=IV': "electrical power",
        'p = mv': "momentum formula",
        'p=mv': "momentum formula",
        'W = Fd': "work done formula",
        'W=Fd': "work done formula",
        'KE = 1/2 mv^2': "kinetic energy formula",
        'PE = mgh': "potential energy formula",
        'F = kx': "Hooke's law",
        'F=kx': "Hooke's law",
        'PV = nRT': "ideal gas law",
        'PV=nRT': "ideal gas law",
        'τ = r × F': "torque formula",
    }

    result = text
    for formula, name in physics_formulas.items():
        if formula in result:
            result = result.replace(formula, name)

    return result


def _convert_common_symbols(text: str) -> str:
    """Convert common math symbols to text."""
    symbol_map = {
        '∑': 'sum',
        '∏': 'product',
        '∫': 'integral',
        '∂': 'partial derivative',
        '∇': 'nabla',
        '∞': 'infinity',
        '±': 'plus or minus',
        '≤': 'less than or equal to',
        '≥': 'greater than or equal to',
        '≠': 'not equal to',
        '≈': 'approximately equal to',
        '∈': 'element of',
        '∉': 'not element of',
        '⊂': 'subset',
        '∪': 'union',
        '∩': 'intersection',
        '→': 'implies',
        '↔': 'if and only if',
        '⇒': 'implies',
        '⇔': 'if and only if',
        'α': 'alpha',
        'β': 'beta',
        'γ': 'gamma',
        'δ': 'delta',
        'θ': 'theta',
        'λ': 'lambda',
        'μ': 'mu',
        'π': 'pi',
        'σ': 'sigma',
        'φ': 'phi',
        'ω': 'omega',
        'Δ': 'delta',
        'Σ': 'sigma',
    }

    result = text
    for symbol, word in symbol_map.items():
        # Only replace if symbol is standalone (not part of a word)
        result = re.sub(rf'(?<!\w){re.escape(symbol)}(?!\w)', word, result)

    return result


def get_formula_description(query: str) -> str | None:
    """Get a natural language description of a formula in the query.

    Returns None if no formula is detected.
    """
    # Check if query contains formula-like patterns
    has_formula = bool(
        re.search(r'[∆δ∑∏∫∂∇±≤≥≠≈∈∉⊂∪∩]', query) or
        re.search(r'[A-Z]\s*=\s*\[', query) or
        re.search(r'\d+\s*\d+\s*\d+', query) or
        re.search(r'[a-z]\s*\d+\s*[A-Z]\s*\d+', query) or
        re.search(r'→|⇌|↑|↓', query)
    )

    if has_formula:
        return formula_to_natural_language(query)
    return None
