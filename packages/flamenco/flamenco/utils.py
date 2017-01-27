import contextlib


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
            # print("Individual frame %d" % (frame))
        elif num_parts == 2:
            frame_start = int(x[0])
            frame_end = int(x[1])
            frames_list += range(frame_start, frame_end + 1)
            # print("Frame range %d-%d" % (frame_start, frame_end))
    frames_list.sort()
    return frames_list


def frame_range_merge(frames_list=None, blender_style=False):
    """Given a frames list, merge them and return them as range of frames.

    :type frames_list: list
    :type blender_style: bool
    :param blender_style: whether to use Blender style frame range notation (3..5) or not (3-5).
    :rtype: str

    :Example:
    >>> frames = [1, 3, 4, 5, 8]
    >>> frame_range_merge(frames)
    u'1,3-5,8'
    >>> frame_range_merge(frames, blender_style=True)
    u'1,3..5,8'
    """
    if not frames_list:
        return ""

    range_sep = '..' if blender_style else '-'

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
            elif start_frame + 1 == prev_frame:
                ranges.append(str(start_frame))
                ranges.append(str(prev_frame))
            else:
                ranges.append(u'{}{}{}'.format(start_frame, range_sep, prev_frame))
            start_frame = current_frame
        prev_frame = current_frame
    if start_frame == current_frame:
        ranges.append(str(start_frame))
    elif start_frame + 1 == current_frame:
        ranges.append(str(start_frame))
        ranges.append(str(current_frame))
    else:
        ranges.append(u'{}{}{}'.format(start_frame, range_sep, current_frame))
    return u','.join(ranges)


def iter_frame_range(merged_frame_range, chunk_size):
    """Generator, iterates over frame chunks.

    Yields lists of frame numbers. Each except the last list is exactly
    'chunk_size' frame numbers long.
    """

    parsed_frames = frame_range_parse(merged_frame_range)

    for chunk_start in range(0, len(parsed_frames), chunk_size):
        chunk_frames = parsed_frames[chunk_start:chunk_start + chunk_size]
        yield chunk_frames


@contextlib.contextmanager
def report_duration(logger, description):
    import time

    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        logger.debug('report_duration: %s took %f seconds', description, end_time - start_time)
