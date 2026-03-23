# FemCAD Syntax Reference (Compact)
# The order of the top level statements in the fcs file that represents gclass is irrelevant
# What is important is the topology of the defined expression tree 
# Every value in fcs file is immutable and often lazy evaluated
# Don't be affraid to introduce more gclasses to achieve your point 
# Think of gclass as a rich 'function' definition with optional imputs and many outputs
# Dynamic objects are less powerfull than gclasses because field definition of dynamic object can not use other field definitions in the same dynamic object


## Core Syntax
```fcs
# Variables
x = 5          # immutable, lazy, non-updatable, 
x := 5         # immutable, lazy, updatable, mem-cached

# Functions (lambda)
fn = x => x * 2
fn = a,b => a + b         # watch out, arguments in lambda definition not in parentheses !

# Conditionals
result = (x > 0) ? "yes" : "no"   # use () whenever operator priories are not clear

# Arrays (0-indexed, immutable)
arr = [1,2,3]
arr[0]         # access
arr.Select(x => x*2)   # map
arr.Where(x => x>1)    # filter
arr.Sum()              # reduce
arr.Aggregate(                     # complex aggregate
  {arr=[],sum=0},                  # initial value for accumulator   
  (acumulator,item =>              # lambda to generate next value 
  {                                # next value is complex object
    arr=acumulator.arr+[item],     # that has growing array
    sum=acumulator.sum+item        # and cumulative sum
  }))

# Dynamic objects (immutable)
obj = {
  a=1,               # field definitions are separated by comma
  b=2                # field definition can not reach other field definitions in the same dynamic object, there is no "this." (use gclass if needed)
}
obj.a                 # access
obj{a=3}              # update (creates new updated instance)

# More elaborate calculation, that needs multiple steps refering each other can not be achieved by dynamic objects
# Multi step calculation can either be achieved by dedicated algoritmic gclass (with very specific name), where each calulation step can be separate field
# or by nested lambda functions, which transform one instance of dynamic object into another.


# Gclasses (is like a normal OOP class, but may contain assembly geometry )
# Each gclass needs one 'ClassName.fcs' file that is defining its fields and assembly
# Also the filename defines implicit class name for the gclass

# following two forms lead to identical gclass reference defintions

gclass {gcMyCar} filename "./MyCar.fcs"   # traditional form: syntax with custom name and custom 
                                          # path to the fcs file, in this folder or other

gcMyCar = MyCar                           # compact form: syntax takes advantage of the implicit 
                                          # class name in the same folder!

# reads and updates of gclasses are then the same as for the dynamic objects
# Because also gclasses are immutable, notice that the class type name 'MyCar' and default value 'gcMyCar' 
# have exactly the same value, therefore both can play the same role in expressions
# So 'MyCar{height=1.2}' is exactly the same value as 'gcMyCar{height=1.2}'
# updater looks like constructor :-)

# Updater syntax shorthand for assigning parameter with variable of the exactly same name
height = 45

mySmallCar = MyCar { height = height }  # this can be shortened to following
mySmallCar = MyCar { height }           # which stil loweres to MyCar { height = height }

# FemCAD does NOT support multi-line “do blocks” inside expressions (no local assignments like:
# { a = ..., b = ..., tmp = ..., tmp2 = ... } with tmp used by b, etc.)

# If a calculation needs multiple dependent steps, use:
# - a dedicated gclass (recommended), possibly several small gclasses chained, or
# - nested lambdas that pass intermediate values explicitly.


## Whitespacing and linebreaks

# Definition of gclass fields starts on column 0 (not indented).

mySmallCar = MyCar {                  # Longer definition may be broken to muliple lines, 
  height = 3,                         # but the line break may happen only inside of {} or brackets () or []
  length = 5                          # Nested lines may be indented for visual clarity
}

## Comments
# single line
# multiline comments do not exist

```

## Naming Conventions
- **Variables**: camelCase (`cubeVolume`, `loadCase`)
- **Types/GClasses**: PascalCase (`BeamStandard`, `ForceArrow`)
- **Geometric IDs**: `{identifier}` braces are part of the syntax in the assembly statements and have no deeper meaning. Sadly, sometimes may be confused with updaters. Luckily, updater may contain white space, while braced identifier may not.
  - `{v1}, {v2}` - vertices
  - `{c1}, {c2}` - curves
  - `{gb}` - gblocks
  - `{l1}` - layers
  - `{cross_section1}` - cross-sections
  
# Selected geometrical objects may exist without explicit name identifier,
# These are vertices, curves, areas (allows buffered geometry representation in memory)

## Assembly Geometry Essentials

```fcs
# Vertices
vertex 0 xyz 0 0 0              # vertex has only zero based integer ID
vertex 1 xyz 7 0 0              # these form a triangle 7x7
vertex 2 xyz 7 7 0            

curve 0 vertex 0 1              # simple oriented lines defined by two vertices
curve 1 vertex 1 2              # buffered geometry indices are zero based, 
curve 2 vertex 2 0              # but not every index needs to be used

area 1 boundary curve +1 +2 +3  # area represented by its outer loop with defined orientations of curves
area 2 boundary curve -1 -3 -2  # another triangle that has oposite oritenation but uses the same curves
```

```fcs
# Vertices
vertex {v1} xyz 0 0 0           # vertex has also a name v1
vertex {v2} xyz 7 0 0           # this is alternative to just IDs
vertex {v3} xyz 7 7 0           # 
vertex {v4} xyz 0 7 0           # 

vertex {vh1} xyz 1 1 0          # these three form a triangular hole
vertex {vh2} xyz 5 1 0          # 
vertex {vh3} xyz 5 5 0            

# Curves
curve {c1} vertex {v1} {v2}     
curve {c2} vertex {v2} {v3}     
curve {c3} vertex {v3} {v4}     
curve {c4} vertex {v4} {v1}     

curve {ch1} vertex {vh1} {vh2}     
curve {ch2} vertex {vh2} {vh3}     
curve {ch3} vertex {vh3} {vh1}     

# Areas
# Area with opening, the orientation of the area respects the right-hand rule
area {a1} boundary curve +{c1} +{c2} +{c3} +{c4} opening curve -{ch3} -{ch2} -{ch1}   


# GBlocks (geometric instances)
gblock {gb1} gclass ClassName{param=value}                             # gblock in GCS
gblock {gb2} gclass ClassName{param=value} lcs GCS.Tx(2)               # gblock shifted in X axis
gblock {gb3} gclass ClassName{param=value} lcs GCS.Tx(2) if condExp    # in assembly only if condExp is True

# Coordinate systems
GCS                   # Global
GCS.Tx(2)             # translate X
GCS.Rz(45*Unit.deg)   # rotate Z by arbitrary angle in radians converted from degrees
GCS.T(x,y,z)          # general translate
GCS.Rz90()            # predefined 4 helper methods for axis e.g. Rx90(), Rx180(), Rx270()

# Transforms: left-applied, simply chained method calls
GCS.Rz(90*Unit.deg).Tx(2)  # rotate first, then translate

# Distribution (multiple instances)
# While gblock represents one (or none) instance of gclass, distribution represents an array of gclasses

# Common pattern for distribution is to first define a custom Part.fcs gclass like this
Class :={}                                # user needs to specify the instance of the gclass that will be placed
Lcs   := GCS                              # and Lcs that will be used for this specific part instance
gblock {gbPart} gclass (Class) lcs (Lcs)  # this is a wrapping gblock fo this part instance

# And then we can insert a distribution of MyCar gclasses like this 

arrayOfParts = [
  Part{Class=MyCar, Lcs=GCS.Tx(1)},                 # place default car on X=1 origin
  Part{Class=MyCar, Lcs=GCS.Tx(2)},                 # place default car on X=2 origin
  Part{Class=MyCar{ length = 0.1}, Lcs=GCS.Tx(3)}   # place shorter car on X=3 origin
]

distribution {d1} gclasses (arrayOfParts)   # The distribution places all gclasses into the GCS, so each one must use a different Lcs.

# Other syntaxes how to space and modify instances exist but are beyond basic concepts.
# The above usage is the most general and covers every possible distribution functionality.
```

## Units & Types
# The underlying runtime for femcad script was implemented in C# and runs on the dotnet runtime. 
# Some of the primitives (bools, ints, doubles ) are reused and extended by strong types from femcad runtime.

```fcs
# Units (runtime conversion to basic units (SI+radians))
force = 10 * Unit.kN    # force will be double with value 10000.0
angle = 45 * Unit.deg   # angle will be double with value 0.7853981633974483
length = 2.5 * Unit.m   # length becomes double of value 2.5

# Trig expects radians (use Unit.deg to convert)
Sin(45 * Unit.deg)      # methods from dotnet runtime System.Math assembly are imported to global namespace
Cos(PI / 4)             # PI is double constant

# Vectors
f = Fcs.Geometry.Vector3D(fx, fy, fz)   # constructs femcad runtime object (Vector3D) of three doubles
```

## FEM Essentials
# beyond basics

## Common Patterns
```fcs
# Resource library
res := Resources{}            # serves a purpose of shared libraries, there is often a Resources.fcs file in each directory
css := res.cssLib.VHP50x50x3

# Part wrapper
Part{Class=Arrow{L=1}, Lcs=GCS.Tx(2)}

# Array operations
forces = parts.Select(p => p.Class.f)
total = forces.Sum()
```

## Key APIs
```fcs
# Converters
Fcs.Converters.EnumerableRange(1, 20)

# Geometry
Fcs.Geometry.Vector3D(x,y,z)

# Analysis
Fcs.Analysis.BeamSection.CharacteristicsSolver(css).Result
Fcs.Analysis.ResultMonitor.New(case, resultType, beams)
Fcs.Analysis.Result.Beam.N    # normal force
Fcs.Analysis.Result.Beam.My   # moment Y
Fcs.Assembly.AllBeams

# Symbols
Fcs.Symbol.Variable{Definition=..., Name=..., Symbol=...}

# Reporting
Fcs.Reporting.Document{TitleBlock=..., Children=[...]}
Fcs.Reporting.Text("...")
Fcs.Reporting.Table{Header=..., Body=[...]}
```

## File Organization
```
Project/
├── main.fcs          # entry point
├── Resources.fcs     # shared libraries
├── Colors.fcs        # layers
└── css/              # cross-sections
```

Files auto-discovered by name (no explicit import):
```fcs
res := Resources{}     # finds Resources.fcs
```

## Critical Rules
- **Case-sensitive**: `Fcs.` not `FCS.`
- **0-indexed arrays**: `arr[0]` is first
- **Immutable objects**: updates create new objects
- **Named parameters**: `Box{B=1, L=2}` (order-independent)
- **Identifiers unique**: `{v1}` cannot be reused
