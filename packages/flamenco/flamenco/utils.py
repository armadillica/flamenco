def frame_range_parse(frame_range=None):
    """Given a range of frames, return a list containing each frame.

    :type frame_range: str
    :rtype: list

    :Example:
    >>> frames = "1,3-5,8"
    >>> frame_range_parse(frames)
    >>> [1, 3, 4, 5, 8]
    """
    if not frame_range:
        return list()

    frames_list = []
    for part in frame_range.split(','):
        x = part.split("-")
        num_parts = len(x)
        if num_parts == 1:
            frame = int(x[0])
            frames_list.append(frame)
            #print("Individual frame %d" % (frame))
        elif num_parts == 2:
            frame_start = int(x[0])
            frame_end = int(x[1])
            frames_list += range(frame_start, frame_end + 1)
            #print("Frame range %d-%d" % (frame_start, frame_end))
    frames_list.sort()
    return frames_list


def frame_range_merge(frames_list=None):
    """Given a frames list, merge them and return them as range of frames.

    :type frames_list: list
    :rtype: str

    :Example:
    >>> frames = [1, 3, 4, 5, 8]
    >>> frame_range_merge(frames)
    >>> "1,3-5,8"
    """
    if not frames_list:
        return ""
    ranges = []
    current_frame = start_frame = prev_frame = frames_list[0]
    n = len(frames_list)
    for i in range(1, n):
        current_frame = frames_list[i]
        if current_frame == prev_frame + 1:
            pass
        else:
            if start_frame == prev_frame:
                ranges.append(str(start_frame))
            else:
                ranges.append("{0}-{1}".format(start_frame, prev_frame))
            start_frame = current_frame
        prev_frame = current_frame
    if start_frame == current_frame:
        ranges.append(str(start_frame))
    else:
        ranges.append("{0}-{1}".format(start_frame, current_frame))
    return ",".join(ranges)
