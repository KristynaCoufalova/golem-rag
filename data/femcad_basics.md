# FemCAD Programming Language - Basics Reference

## Overview
FemCAD is a domain-specific language for structural engineering, finite element analysis (FEM), and geometric modeling. It combines scripting capabilities with engineering-specific constructs.

## File Extensions
- `.fcs` - FemCAD Script files
- `.fcsdrs` - FemCAD drawing/settings files

---

## 1. BASIC SYNTAX & CONVENTIONS

### Comments
```fcs
# Single line comment
##############################
# Section header comment
##############################
```

### Variable Assignment
```fcs
# Mutable binding (can be reassigned within scope)
variableName = value
variableName = newValue  # OK - rebinding allowed

# Single-assignment definition (cannot be rebound; like const/parameter)
variableName := value
# variableName := newValue  # ERROR - cannot rebind
```

**Rule**: Use `:=` for parameters and values that should not change (compile-time semantics). Use `=` for variables that may be reassigned.

### Naming Conventions
- **Variables**: camelCase (e.g., `cubeVolume`, `dailyTemperatures`)
- **Functions**: camelCase, optionally with `Fn` suffix (e.g., `addOne` or `addOneFn`, `discriminant` or `discriminantFn`)
  - *Note*: The `Fn` suffix is a FemCAD convention for clarity but is not required
- **GClasses/Types**: PascalCase (e.g., `BeamStandard`, `ForceArrow`)
- **Identifiers with braces**: Used for geometric entities
  - `{p1}` - point identifier
  - `{v1}`, `{v2}` - vertex identifiers
  - `{c1}` - curve identifier
  - `{gb}`, `{gbOrigin}` - gblock identifiers
  - `{l1}`, `{lRed}` - layer identifiers
  - `{cross_section1}` - cross-section identifier

---

## 2. DATA TYPES

### Numbers
```fcs
# Integer
cubeSide = 2
cubeVolume = Pow(cubeSide, 3)

# Float (implicit)
temperature = 22.5
angle = 45 * Unit.deg  # With units
force = 15 * Unit.kN   # Force with units
```

**Units & Type Safety**:
- FemCAD performs dimension checking at runtime
- Physical quantities should always include units (e.g., `Unit.kN`, `Unit.mm`, `Unit.deg`)
- Trigonometric functions (Sin, Cos, Tan) expect **radians** unless you multiply by `Unit.deg`
- Common units: `Unit.deg` (degrees), `Unit.kN` (kilonewtons), `Unit.mm` (millimeters), `Unit.m` (meters)

### Strings
```fcs
name = "John"
greeting = "Hello " + name  # String concatenation
message = "Temperature: " + temperature  # Implicit conversion
```

### Arrays
```fcs
# Array declaration (0-indexed)
dailyTemperatures = [-3, 25, 22, 23, 24]

# Array access
tuesdayTemperature = dailyTemperatures[1]  # Returns 25 (2nd element)

# Array concatenation
weekTemperatures = dailyTemperatures + [26, 27]

# Generate ranges
numbers = Fcs.Converters.EnumerableRange(1, 20)  # [1,2,3,...,20]
```

**LINQ-style Array Operations** (inspired by C# LINQ):
```fcs
# Core methods available on all arrays:
array.Select(fn)      # Map - transform each element
array.Where(fn)       # Filter - keep elements matching predicate
array.Sum()           # Sum all elements
array.Count()         # Count elements
array.Any(fn)         # True if any element matches predicate
array.All(fn)         # True if all elements match predicate
array.Aggregate(initial, accumulator)  # Reduce/fold operation

# Examples
evens = [1,2,3,4].Where(x => x % 2 == 0)  # [2,4]
doubled = [1,2,3].Select(x => x * 2)      # [2,4,6]
total = [1,2,3,4].Sum()                   # 10
```

### Dynamic Objects
```fcs
# Object literal with properties
resultObject = {
   betterTemps = [26, 23, 24, 25],
   worseTemps = [20, 17, 18, 19]
}

# Object with nested properties
tuesday = { 
   temperature = 5, 
   message = "sunny" 
}

# Access properties
tuesdayMessage = tuesday.message

# Object update (creates NEW object via copy-on-write)
czechTuesday = tuesday{ message = "slunecno", extra = 4 }
# Original 'tuesday' object is unchanged

# Nested updates (shallow update semantics)
# To update nested properties, you must explicitly update each level:
outer = { inner = { value = 1 } }
updated = outer{ inner = outer.inner{ value = 2 } }
```

**Immutability**: All objects are immutable. Updates use copy-on-write semantics and create new objects. Nested updates are shallow - you must explicitly update each level of nesting.

---

## 3. FUNCTIONS

### Function Definition (Lambda syntax)
```fcs
# Simple lambda
addOne = o => (o + 1)
addOneFn = o => (o + 1)  # With Fn suffix (convention, not required)

# Multi-parameter lambda
discriminant = (a, b, c) => sqrFn(b) - 4*a*c

# Lambda with complex body
improveArray = (array, modifFn) => (
   array.Select(o => modifFn(o))
)
```

### Function Calls
```fcs
# Simple call
answer = addOne(41)  # Returns 42

# Array methods with lambdas
improvedWeekTemps = dailyTemperatures.Select(o => (o + 1))
worseWeekTemps = dailyTemperatures.Select(o => (o - 5))
```

### Built-in Functions
```fcs
# Math
Pow(base, exponent)
Sqrt(value)
Sin(angle)    # Expects radians
Cos(angle)    # Expects radians
Tan(angle)    # Expects radians

# Usage with degrees
angleDeg = 45 * Unit.deg
sinValue = Sin(angleDeg)  # Unit.deg converts to radians

# Array operations
array.Select(lambda)      # Map operation
array.Where(predicate)    # Filter operation
array.Sum()               # Sum all elements
array.Aggregate(initial, accumulator)  # Reduce/fold
```

---

## 4. CONTROL STRUCTURES

### Conditional Expressions (Ternary)
```fcs
# Syntax: (condition) ? (trueValue) : (falseValue)
tuesdayIsWarm = tuesdayTemperature > 18

tuesdayMessage = ((tuesdayIsWarm) 
   ? ("Tuesday is warm")  # English: "Tuesday is warm"
   : ("Tuesday is cold")  # English: "Tuesday is cold"
)

# Inline conditional
result = (temp > 18) ? "warm" : "cold"
```

### Array Transformations
```fcs
# Map with conditional logic
nextWeekTemps = dailyTemperatures.Select(temp => 
   "Today is " + ((temp > 18) ? "warm" : "cold") + ", it's " + temp + " degrees"
)

# Complex transformation creating objects
nextWeek = dailyTemperatures.Select(temp => {
   temperature = temp, 
   message = "Today is " + ((temp > 18) ? "warm" : "cold")
})
```

### Aggregate Pattern (Fold/Reduce)
```fcs
# Accumulator pattern for stateful iteration
# Useful for building up state while iterating through arrays
arrayClasses2 = arrayClasses.Aggregate( 
   {o = Fcs.Geometry.Vector3D(0, 0, 0), a = []}  # Initial accumulator state
   ,
   (acc, elem) => {  # Accumulator function: (currentState, currentElement) => newState
      o = acc.o + elem.Class.f,
      a = acc.a + [Part{Class = elem.Class, Lcs = GCS.T(acc.o[0], acc.o[1], acc.o[2])}]
   }   
)
```

---

## 5. GEOMETRIC ENTITIES

### Coordinate Systems

**GCS vs LCS**:
- **GCS** = Global Coordinate System (world coordinates)
- **LCS** = Local Coordinate System (relative to parent or transformed GCS)
- Transforms are **left-applied** (compose right-to-left): `GCS.Rz(45*Unit.deg).Tx(2)` means "rotate first, then translate"

```fcs
GCS              # Global Coordinate System

# Transformations
GCS.Tx(2)        # Translate X by 2
GCS.Ty(6)        # Translate Y by 6
GCS.Tz(4)        # Translate Z by 4
GCS.T(x, y, z)   # General translation

# Rotations
GCS.Rz90()       # Rotate 90° around Z
GCS.Ry270()      # Rotate 270° around Y
GCS.Rz(phi * Unit.deg)  # Rotate by angle around Z
GCS.Ry(PI/2 - theta * Unit.deg)  # Rotate around Y

# Chaining transformations (left-applied, right-to-left composition)
GCS.Rz(phi * Unit.deg).Ry(PI/2 - theta * Unit.deg)  # Rotate around Y first, then around Z
```

### Vertices
```fcs
# Named vertex with coordinates
vertex {v1} xyz 0 0 0
vertex {v2} xyz 1 0 0

# Numbered vertices (alternative syntax)
vertex 1 xyz 0 1 0
vertex 2 xyz 0 0 0
vertex 3 xyz 0.25 0 0
vertex 4 xyz 0.25 1 0
```

### Curves
```fcs
# Curve connecting vertices
curve {c1} vertex {v1} {v2}

# Multiple curves (numbered)
curve 1 vertex 1 2
curve 2 vertex 2 3
curve 3 vertex 3 4
curve 4 vertex 4 1
```

### Areas
```fcs
# Area defined by boundary curves
# Curves prefixed with + or - to indicate direction
area 1 boundary curve +1 +2 +3 +4
area 2 boundary curve +5 +6 +7 +8
```

### Volumes
```fcs
# Prism volume from two areas with layer
volume {v1} prism 1 2 layer (l1)
```

---

## 6. GCLASS SYSTEM (Geometric Classes)

### GClass Definition
```fcs
# GClass = reusable geometric component template (like a class or component)
# Think of GClass as a blueprint for creating geometric instances

# Simple GClass with parameters
w := 0.04
gblock {gbLx} gclass BoxLine{l1 = Colors.lRed, w = w}

# GClass with transformations
gblock {gbLy} gclass BoxLine{l1 = Colors.lGreen, w = w} lcs GCS.Rz90()
```

**GClass Parameter Binding**: Parameters are bound **by name** (order-independent), not positionally.
```fcs
# These are equivalent:
gblock {gb1} gclass Box{B = 1, L = 2, H = 3}
gblock {gb2} gclass Box{H = 3, B = 1, L = 2}
```

### GBlock (Geometric Block)
```fcs
# Basic syntax: gblock {identifier} gclass ClassName{params} lcs coordinateSystem
# Parentheses around ClassName{params} are optional but recommended for clarity with expressions

# Simple gblock (no parentheses needed)
gblock {gbOrigin} gclass Origin

# GBlock with parameters (parentheses optional)
gblock {gbBox} gclass Box{l1 = Colors.lGreen} lcs GCS.Tx(2)

# GBlock with expression (parentheses recommended for clarity)
gblock {gbForce} gclass (Arrow{L = force, l1 = l1}) lcs (GCS.Rz(phi * Unit.deg))
```

### Parametric GClasses
```fcs
# Define reusable components with parameters
L := 1
w := 0.03
l1 := Colors.lForce

gblock {gbLeg} gclass (Box{B = w, L = w, H = 0.75*L, l1 = l1}) lcs GCS.T(-0.5*w, -0.5*w, 0)

gblock {gbHead} gclass (Spike{B = 3*w, L = 3*w, H = 0.25*L, l1 = l1}) lcs GCS.T(-1.5*w, -1.5*w, 0.75*L)
```

### Part Pattern (Wrapper)
```fcs
# Part is a common pattern for wrapping GClasses with a local coordinate system
# This pattern makes it easy to create positioned instances of geometric components

Class := {}
Lcs := GCS
gblock {gb} gclass (Class) lcs (Lcs)

# Usage examples
Part{Class = ForceArrow{force = 7, phi = 145, theta = 60}}
Part{Class = Box{l1 = Colors.lPoint}, Lcs = GCS.Tx(4)}
```

### Distribution (Multiple GBlocks)
```fcs
# Create multiple gblocks from an array of classes
arrayClasses = [ 
    Part{Class = ForceArrow{force = 7, phi = 145, theta = 60}},
    Part{Class = ForceArrow{force = 2, phi = -120, theta = 30}},
    Part{Class = ForceArrow{force = 3, phi = 30, theta = -45}}
]

distribution {d1} gclasses (arrayClasses)
```

---

## 7. LAYERS & VISUALIZATION

### Layer Definition
```fcs
# Layer with color name
layer {l1} color Blue

# Layer with ARGB color (Alpha, Red, Green, Blue)
layer {lResult} color (Argb(255, 205, 0, 0))  # Opaque red

# Common color names
layer {lRed} color Red
layer {lGreen} color Green
layer {lBlue} color Blue
layer {lPoint} color Yellow
```

### Colors Module Pattern
The `Colors` namespace (e.g., `Colors.lRed`) comes from a conventional `Colors.fcs` file that you include in your project:

```fcs
# Colors.fcs - conventional file for layer definitions
############################
##   FemCAD script file   ##
############################

layer {lResult}  color (Argb(255, 205, 0, 0))
layer {lForce}   color (Argb(50, 0, 100, 0))
layer {lPoint}   color Yellow

layer {lRed}   color Red
layer {lGreen} color Green
layer {lBlue}  color Blue
```

Then reference these in your code:
```fcs
gblock {gbBox} gclass Box{l1 = Colors.lRed}
```

---

## 8. UNITS & PHYSICAL QUANTITIES

### Unit System
```fcs
# Angles
angle = 45 * Unit.deg       # Degrees
theta = PI/4                # Radians (no unit needed)

# Forces
force1 = 15 * Unit.kN       # Kilonewtons

# Lengths
length = 2.5 * Unit.m       # Meters
width = 250 * Unit.mm       # Millimeters

# Built-in constants
PI  # Mathematical constant π
```

**Important**: Trigonometric functions expect **radians** unless you use `Unit.deg`:
```fcs
# These are equivalent:
result1 = Sin(45 * Unit.deg)
result2 = Sin(PI / 4)
```

### Vector Operations
```fcs
# 3D Vector
f = Fcs.Geometry.Vector3D(fx, fy, fz)

# Vector arithmetic
resultant = vector1 + vector2
sumOfForces = arrayOfVectors.Sum()

# Vector components (0-indexed)
fx = forceVector[0]
fy = forceVector[1]
fz = forceVector[2]
```

---

## 9. FEM ANALYSIS

### Material Definition
```fcs
material 1 rho 7850 alpha 1.2E-05 lambda 40 c 440 linear E 210.0E9 ni 0.2
# Parameters:
# rho: density [kg/m³]
# alpha: thermal expansion coefficient [1/K]
# lambda: thermal conductivity [W/(m·K)]
# c: specific heat [J/(kg·K)]
# linear: linear elastic behavior
# E: Young's modulus [Pa]
# ni: Poisson's ratio [-]
```

### Cross-Section Definition
```fcs
# First, solve for cross-section characteristics
ch := Fcs.Analysis.BeamSection.CharacteristicsSolver(beamCss).Result

# Then define the cross-section for FEM analysis
cross_section {cross_section1} geometry_class (beamCss) material 1 parameters {
  A = ch.EA,           # Area
  ey = -ch.ESzs/ch.EA, # Centroid offset Y
  ez = -ch.ESys/ch.EA, # Centroid offset Z
  Iy = ch.EIyc,        # Moment of inertia Y
  Iz = ch.EIzc,        # Moment of inertia Z
  Dyz = ch.EDyzc,      # Product of inertia
  Ik = ch.EIyc + ch.EIzc,  # Torsional constant
  Az = 0.0016*5/6,     # Shear area Z
  Ay = 0.0016*5/6      # Shear area Y
}
```

### Model Configuration
```fcs
model_shell3d                    # Model type: 3D shell/beam model
OneMeshElementPerBeam = False    # Multiple elements per beam allowed
Mesh.ElementSize = 0.2           # Target element size [m]
```

### Beam Elements
```fcs
beam {b1} type Frame curve {c1} xsection {cross_section1}
```

### Supports
```fcs
# Fixed support (all DOFs constrained)
support 1 vertex {v1} 0 0 0 0 0 0 fixed "uxuyuzrxryrz"
# DOF string format: "uxuyuzrxryrz"
#   ux, uy, uz = translation in X, Y, Z
#   rx, ry, rz = rotation around X, Y, Z

# Partial restraints (e.g., pinned support - translations fixed, rotations free)
support 2 vertex {v2} 0 0 0 0 0 0 fixed "uxuyuz"
```

### Load Cases
```fcs
loadCase := {
   Name := "SnowFull",
   ActionType := "Variable",      # Variable, Permanent, Accidental
   Specification := "",
   LoadType := "Static"           # Static, Dynamic
}
```

### Loads
```fcs
# Distributed load on curve (force per unit length)
load {loadSW1} curve c1 constant 0 0 -1 0 0 0 case (loadCase)
# Format: Fx Fy Fz Mx My Mz [force/length] [moment/length]

# Point load on vertex
load {loadForce} vertex v2 0 0 -5 0 0 0 case (loadCase)
# Format: Fx Fy Fz Mx My Mz [force] [moment]
```

### Solving & Accessing Results

After defining the model, FemCAD automatically solves when you run the script. Access results via Result Monitors:

```fcs
# Define result monitors for a load case
BeamResultMonitors := loadCase => {
   N := [Fcs.Analysis.ResultMonitor.New(loadCase, Fcs.Analysis.Result.Beam.N, Fcs.Assembly.AllBeams)],
   My := [Fcs.Analysis.ResultMonitor.New(loadCase, Fcs.Analysis.Result.Beam.My, Fcs.Assembly.AllBeams)],
   Mz := [Fcs.Analysis.ResultMonitor.New(loadCase, Fcs.Analysis.Result.Beam.Mz, Fcs.Assembly.AllBeams)],
}

# Create specific load case references
SnowFullCase := Fcs.Action.LoadCase{Name = "SnowFull"}
UlsCase := Fcs.Action.ResultClass{Name = "All ULS-Fundamental"}

# Access results
SnFl := BeamResultMonitors(SnowFullCase)
Uls := BeamResultMonitors(UlsCase)

# Use results (they're automatically computed after solve)
maxMoment = SnFl.My  # Access bending moment results
```

**FEM Analysis Pipeline**:
1. Define geometry (vertices, curves)
2. Define materials and cross-sections
3. Configure model (model type, mesh settings)
4. Create beam elements
5. Apply boundary conditions (supports)
6. Define load cases and apply loads
7. **Solve** (automatic when script runs)
8. Access results via Result Monitors

---

## 10. REPORTING

### Minimal Report
```fcs
inputName = "User"

mainMessageFn = name => name + "'s structural analysis"

minimalReport1 := Fcs.Reporting.Document{
  TitleBlock = "Structural Analysis Report",
  Children = [
     Fcs.Reporting.Text("This is a minimal report"),
     Fcs.Reporting.Text(rw => mainMessageFn(inputName))
  ]
}

# Display the report
# browse_report minimalReport1
```

### Symbol Variables
```fcs
force1 = Fcs.Symbol.Variable{
  Definition = 15 * Unit.kN,
  Name = "force1",
  Symbol = "F_1",
  Explanation = "force number 1",
  QuantityType = Fcs.EngineeringQuantity.BeamInternalForce
}

force2 = Fcs.Symbol.Variable{
  Definition = 25 * Unit.kN,
  Name = "force2",
  Symbol = "F_2",
  Explanation = "force number 2",
  QuantityType = Fcs.EngineeringQuantity.BeamInternalForce
}

total = Fcs.Symbol.Variable{
    Definition = force1 + force2,
    Name = "totalForce",
    Symbol = "F_{total}",
    QuantityType = Fcs.EngineeringQuantity.BeamInternalForce
}

# Get all variables used in the definition
list = total.GetDefinitionVariableSymbols()
```

### Report Tables
```fcs
tab1 := Fcs.Reporting.Table{
  Header := Fcs.Reporting.Table.Row("Symbol", "Definition", "Value", "Unit", "Explanation"),
  Body := [Fcs.Reporting.Table.Row(Fcs.Reporting.Symbol(total, "SED"))]
    + list.Select(s => 
        Fcs.Reporting.Table.Row(
           Fcs.Reporting.Symbol(s, "S"),   # Symbol
           Fcs.Reporting.Symbol(s, "Eu"),  # Expression with unit
           Fcs.Reporting.Symbol(s, "V"),   # Value
           Fcs.Reporting.Symbol(s, "u"),   # Unit
           Fcs.Reporting.Symbol(s, "X")    # Explanation
        )
    )
}
```

### Structured Reports
```fcs
doc1 := Fcs.Reporting.Document{
  DefaultSetup = Fcs.Reporting.Setup{Collapsible = False, LatexSyntax = True},	
  TitleBlock = Fcs.Reporting.Symbol(total, "SADEuVu"),
  Children = [
     tab1,
     Fcs.Reporting.Symbol(total, "SADEuVu")
  ]
}

# Display the report
# browse_report doc1
```

### Symbol Format Codes
Use these codes with `Fcs.Reporting.Symbol(variable, "formatCodes")`:
- `S` - Symbol (e.g., F₁)
- `A` - Alternative representation
- `D` - Definition (formula)
- `E` - Expression (evaluated)
- `u` - Unit (e.g., kN)
- `V` - Value (numeric)
- `X` - Explanation (description text)

---

## 11. COMMON PATTERNS

### Resource Pattern
```fcs
# Resources.fcs typically contains shared cross-section libraries
res := Resources{}
beamCss := res.cssLib.VHP50x50x3
```

### Characteristic Solver Pattern
```fcs
# Compute cross-section properties before creating FEM cross-section
ch := Fcs.Analysis.BeamSection.CharacteristicsSolver(beamCss).Result
# ch now contains: EA, EIyc, EIzc, EDyzc, ESys, ESzs, etc.
```

### Force Calculation Pattern
```fcs
# Convert spherical coordinates (magnitude, phi, theta) to Cartesian (fx, fy, fz)
force = 10  # Magnitude
phi = 45 * Unit.deg    # Azimuthal angle
theta = 30 * Unit.deg  # Polar angle

fx = force * Cos(phi) * Cos(theta)
fy = force * Sin(phi) * Cos(theta)
fz = force * Sin(theta)

f = Fcs.Geometry.Vector3D(fx, fy, fz)
```

### Array to Object Pattern
```fcs
# Extract properties from array of objects
arrayOfForces = arrayClasses.Select(o => o.Class.f)
resultingForce = arrayOfForces.Sum()
```

---

## 12. IMPORTANT NOTES

### Case Sensitivity
- FemCAD is **case-sensitive**
- Convention: PascalCase for types, camelCase for variables
- Namespaces: `Fcs.` (not `FCS.` or `fcs.`)

### Assignment Operators
- `=` - Mutable binding (can be reassigned in same scope)
- `:=` - Single-assignment definition (cannot be rebound; like const)

### Object Immutability
- Objects are **immutable**
- Updates create new objects via copy-on-write: `newObj = oldObj{prop = newValue}`
- Nested updates are **shallow** - must explicitly update each level

### Array Indexing
- Arrays are **0-indexed**
- `array[0]` is the first element

### Namespace Conventions
- `Fcs.` - Framework/library namespace prefix (case-sensitive!)
- `GCS.` - Global Coordinate System operations
- `Unit.` - Physical unit definitions

### Geometric Entity Identifiers
- Use braced identifiers `{id}` for all geometric entities
- Identifiers must be **unique** within their scope
- Convention: prefix with entity type (e.g., `{v1}` for vertex, `{c1}` for curve, `{gb}` for gblock)

---

## 13. COMMON API PATTERNS

### Fcs.Converters
```fcs
Fcs.Converters.EnumerableRange(start, end)  # Generate integer sequence [start...end]
```

### Fcs.Geometry
```fcs
Fcs.Geometry.Vector3D(x, y, z)  # 3D vector constructor
```

### Fcs.Analysis
```fcs
Fcs.Analysis.BeamSection.CharacteristicsSolver(css).Result
Fcs.Analysis.ResultMonitor.New(loadCase, resultType, beams)
Fcs.Analysis.Result.Beam.N     # Normal force
Fcs.Analysis.Result.Beam.My    # Bending moment Y
Fcs.Analysis.Result.Beam.Mz    # Bending moment Z
Fcs.Analysis.Result.Beam.Central.My   # Central moment Y
Fcs.Analysis.Result.Beam.Central.Mz   # Central moment Z
```

### Fcs.Symbol
```fcs
Fcs.Symbol.Variable{...}
Fcs.Symbol.Constant(value, quantityType)
```

### Fcs.Reporting
```fcs
Fcs.Reporting.Document{...}
Fcs.Reporting.Setup{...}
Fcs.Reporting.Text(content)
Fcs.Reporting.Table{...}
Fcs.Reporting.Table.Row(...)
Fcs.Reporting.Symbol(variable, formatCode)
```

### Fcs.Assembly
```fcs
Fcs.Assembly.AllBeams  # Reference to all beam elements in the model
```

### Fcs.Action
```fcs
Fcs.Action.LoadCase{Name = "..."}
Fcs.Action.ResultClass{Name = "..."}
```

### Fcs.EngineeringQuantity
```fcs
Fcs.EngineeringQuantity.BeamInternalForce
# Other quantity types available for dimensional checking
```

---

## 14. FILE STRUCTURE & MODULE SYSTEM

### Typical Project Organization
```
Project/
├── main.fcs              # Main entry point
├── Resources.fcs         # Shared resources/libraries
├── Colors.fcs            # Layer/color definitions
├── BeamStandard.fcs      # Reusable beam components
├── ForceArrow.fcs        # Custom geometric components
└── css/                  # Cross-section definitions
    ├── VHP_profile.fcs
    └── VHP50x50x3.fcs
```

### File Inclusion & References

FemCAD uses **implicit file inclusion** based on file references:
- When you reference a name like `Resources`, `Colors`, or `BeamStandard` that's not defined in the current file, FemCAD looks for a `.fcs` file with that name in the same directory
- No explicit `import` or `include` statement needed
- Files are evaluated in dependency order

```fcs
# In main.fcs - no explicit import needed
res := Resources{}           # Automatically finds Resources.fcs
gblock {gb} gclass BeamStandard  # Automatically finds BeamStandard.fcs
layer {l1} color Colors.lRed     # Automatically finds Colors.fcs
```

### Component File Pattern
```fcs
# BeamStandard.fcs - defines a reusable beam configuration
res := Resources{}

support1 := "uxuyuzrxryrz"
l := 1
beamCss := res.cssLib.VHP50x50x3

vertex {v1} xyz 0 0 0
vertex {v2} xyz l 0 0
curve {c1} vertex {v1} {v2}

material 1 rho 7850 alpha 1.2E-05 lambda 40 c 440 linear E 210.0E9 ni 0.2
# ... rest of beam definition

# Then in main.fcs:
gblock {gb} gclass BeamStandard lcs GCS.Ry(15*Unit.deg)
```

### Best Practices
- Keep geometric component definitions in separate files
- Use descriptive names matching the GClass name (e.g., `ForceArrow.fcs` defines `ForceArrow`)
- Maintain a `Resources.fcs` file for shared libraries and cross-sections
- Organize complex cross-sections in a `css/` subdirectory
- Use `Colors.fcs` for consistent layer definitions across the project

---

## 15. QUICK REFERENCE: SYNTAX AT A GLANCE

```fcs
# Variables
x = 5                           # Mutable
x := 5                          # Immutable (single-assignment)

# Functions
fn = x => x * 2
fn = (x, y) => x + y

# Arrays
arr = [1, 2, 3]
arr[0]                          # Access (0-indexed)
arr.Select(x => x * 2)          # Map
arr.Where(x => x > 1)           # Filter
arr.Sum()                       # Reduce

# Objects
obj = {a = 1, b = 2}
obj.a                           # Property access
obj{a = 3}                      # Immutable update (creates new object)

# Conditionals
result = (x > 0) ? "pos" : "neg"

# Geometry
vertex {v1} xyz 0 0 0
curve {c1} vertex {v1} {v2}
gblock {gb} gclass Box{B = 1, L = 2, H = 3} lcs GCS.Tx(2)

# Units
force = 10 * Unit.kN
angle = 45 * Unit.deg
length = 2.5 * Unit.m

# Comments
# Single line comment
```

---

This reference covers the fundamental syntax, conventions, and patterns needed to understand and write FemCAD code. For domain-specific engineering calculations or advanced features, refer to the official FemCAD documentation at https://github.com/HiStructClient/femcad-doc/wiki
