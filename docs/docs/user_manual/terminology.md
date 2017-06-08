# Terminology

This section briefly explains the main terminology of Flamenco.

**Client**: Software that allows the creation of new Jobs. The
[Blender Cloud Add-on](https://cloud.blender.org/services#blender-addon) is a Client. It
communicates with the Server, and allows the creation of new Jobs from Blender's user
interface.

**Server**: The central point of Flamenco, usually `https://cloud.blender.org/`, but you can install
your own Server too. It compiles the Jobs it receives from the Client into Tasks, and provides the
web interface to manage Jobs, Tasks, and Managers.

**Manager**: Controls a render farm; each farm has one Manager. The Manager receives Tasks from the
Server, and schedules them for execution by its Workers. Workers send their logs and Task updates
to the Manager, which forwards those to the Server.

**Worker**: Executes Tasks it receives from its Manager. A render farm consists of one or more
Workers. Each Worker runs a single Task at a time.

**Job**: Highest level description of an operation to perform. A Job consists of the job description
itself, and a list of one or more Tasks.

**Task**: A collection of one or more Commands. A Worker runs one Task at a time, by executing each
of its Commands in order. If a Command fails, the task fails, and if all Commands succeed, the
Task is marked as "completed". Tasks have a priority and can depend on other Tasks to allow for
complex scheduling.

**Command**: Lowest level description of an operation to perform. A Command represents an operation
such as "Blender render file X.blend from frame Y to frame Z", "move file from A to B", "encode
video with these options", etc.
