"""
Prompt: 
Generate doc strings for a simple method to calculate area of a circle.
"""
import math

def calculate_area(radius):
    """
    --- Google-style docstring --- 
    Return the area of a circle with the given radius.
    The formula used is area = π * radius ** 2.
    Args:
        radius (int | float): Radius of the circle. Must be a non-negative number.
    Returns:
        float: The computed area.
    Raises:
        TypeError: If radius is not a number.
        ValueError: If radius is negative.
    Examples:
        >>> calculate_area(1)
        3.141592653589793
        >>> calculate_area(2.5)
        19.634954084936208
    """
    """
    --- Numpy-style docstring ---
    Return the area of a circle with the given radius.
    Parameters
    ----------
    radius : int or float
        Radius of the circle. Must be non-negative.
    Returns
    -------
    float
        The computed area (π * radius^2).
    Raises
    ------
    TypeError
        If radius is not a number.
    ValueError
        If radius is negative.
    Examples
    --------
    >>> calculate_area(1)
    3.141592653589793
    """
    # Basic type check (allowing ints and floats)
    if not isinstance(radius, (int, float)):
        raise TypeError("radius must be a number (int or float)")
    # Non-negative check
    if radius < 0:
        raise ValueError("radius must be non-negative")
    return math.pi * (radius ** 2)