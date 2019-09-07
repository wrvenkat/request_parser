#!/bin/bash
jython_path=~/Downloads/Jython/jython.jar;
modules="requests settings uploadhandlers";
for module in $modules; do
 java -jar "$jython_path" -m request_parser.tests."$module"."$module"
done