# IFC4.x change detection

With the https://github.com/buildingSMART/IFC4.3.x-development buildingSMART has opted to represent the IFC specification (Schema, Property Sets, Documentation) as a UML model and collection of Markdown files. In the current situation it's still hard to obtain minimal differences between successive commits. Also, the differences computed on the UML model might not always be comprehensible by people used to only reading the generated EXPRESS schema or Property Set definitions.

Therefore, this repository provides an automated means to iterate over commits on the UML repository, generate artefacts and compute diffs on the generated artefacts. The changes are categorized and grouped by means of a YAML file that can isolate changes based on "patch hunks" or files.
