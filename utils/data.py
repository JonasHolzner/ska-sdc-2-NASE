import numpy as np


def create_data_set(df, hi_data, wcs, prob_galaxy, side_length, precuation, freq_band, spatial_points,
                    freq_points_f=None, seed=None):
    data = dict()
    positions = wcs.all_world2pix(df[['ra', 'dec', 'central_freq']], 0).astype(np.int)
    sourcemap = create_sourcemap(positions, hi_data.shape)
    positions = positions[:, :2]
    lower_freq, upper_freq = freq_boundary(df['central_freq'].values, df['w20'].values)
    upper_band = wcs.all_world2pix(
        np.concatenate((df[['ra', 'dec']].values, lower_freq.reshape(lower_freq.shape[0], 1)), axis=1), 0).astype(
        np.int)[:, 2]
    lower_band = wcs.all_world2pix(
        np.concatenate((df[['ra', 'dec']].values, upper_freq.reshape(upper_freq.shape[0], 1)), axis=1), 0).astype(
        np.int)[:, 2]
    part_size = ((upper_band - lower_band) / freq_band).astype(int)
    if freq_points_f is None:
        freq_points_f = np.arange(np.min(part_size), np.max(part_size) + 1) * 2 + 1
    elif type(freq_points_f) == int:
        freq_points_f = np.ones(np.max(part_size) - np.min(part_size) + 1, dtype=np.int) * freq_points_f

    df_size = df.shape[0]
    total_freq_p = np.sum(np.bincount(part_size) * freq_points_f)
    n_sources = total_freq_p * spatial_points
    freq_empty = int(total_freq_p / df_size)
    n_cubes = int(((1 - prob_galaxy) * n_sources) / (prob_galaxy * freq_empty))
    n_empty = n_cubes * freq_empty
    n_points = n_sources + n_empty

    data['image'] = np.zeros((n_points, freq_band, side_length, side_length))
    data['sourcemap'] = np.zeros((n_points, side_length, side_length), dtype=np.int)
    data['position'] = np.zeros((n_points, 3, 2), dtype=np.int)
    data['class'] = np.array([1 if i < n_sources else 0 for i in range(n_points)])
    data['cluster'] = np.zeros(n_points, dtype=np.int)
    rand = Randomizer(seed)

    # Sources Data
    counter = 0
    cluster = 0
    for i in range(df_size):
        l_band = lower_band[i]
        u_band = upper_band[i]
        source_pos = positions[i]

        x, y = random_center_box(rand.rr_sample(spatial_points, 2), side_length, source_pos, precuation, [0, 0],
                                 [hi_data.shape[1], hi_data.shape[2]])
        freq = random_in_interval(rand.rr_sample(freq_points_f[part_size[i]], 1), np.array([[l_band, u_band]]),
                                  freq_band)[0]
        for j in range(spatial_points):
            for k in range(freq_points_f[part_size[i]]):
                data['image'][counter] = hi_data[freq[k, 0]:freq[k, 1], x[j, 0]:x[j, 1], y[j, 0]:y[j, 1]]
                data['sourcemap'][counter] = np.sum(sourcemap[freq[k, 0]:freq[k, 1], x[j, 0]:x[j, 1], y[j, 0]:y[j, 1]],
                                                    axis=0)
                data['position'][counter] = np.array([freq[k], x[j], y[j]])
                data['cluster'][counter] = cluster
                counter += 1
        cluster += 1

    # Empty Data
    while counter < n_points:
        coordinate = (rand.sample(1, 3) * hi_data.shape).astype(np.int)[0]
        l_band = coordinate[0]
        u_band = l_band + freq_empty * freq_band
        freq = random_in_interval(rand.rr_sample(freq_empty, 1), np.array([[l_band, u_band]]), freq_band)[0]
        freq = inside_box([freq], [0], [hi_data.shape[0]])[0]
        x, y = random_center_box(np.array([[0.5, 0.5]]), side_length, coordinate[1:], 0, [0, 0],
                                 [hi_data.shape[1], hi_data.shape[2]])
        sum_map = np.sum(sourcemap[np.min(freq):np.max(freq), x[0, 0]:x[0, 1], y[0, 0]:y[0, 1]])
        if sum_map == 0:
            for i in range(freq_empty):
                data['image'][counter] = hi_data[freq[i, 0]:freq[i, 1], x[0, 0]:x[0, 1], y[0, 0]:y[0, 1]]
                data['position'][counter] = np.array([freq[i], x[0], y[0]])
                data['cluster'][counter] = cluster
                counter += 1
            cluster += 1
    return data


def create_sourcemap(positions, dimensions):
    sourcemap = np.zeros(dimensions, dtype=np.int)
    for pos in positions:
        sourcemap[pos[2], pos[0], pos[1]] = 1
    return sourcemap


class Randomizer:

    def __init__(self, seed=None):
        self.seed = seed
        self.counter = 0
        if seed is None:
            import sobol_seq
            self.rand = lambda n, d, s: sobol_seq.i4_sobol_generate(d, n, s)
            self.reset_f = lambda x: None
        else:
            self.rand = lambda n, d, s: np.random.uniform(size=(n, d))
            self.reset_f = lambda x: np.random.seed(x)

    def reset(self):
        self.counter = 0
        self.reset_f(self.seed)

    def sample(self, n, d):
        s = self.rand(n, d, self.counter)
        self.counter += n
        return s

    def rr_sample(self, n, d):
        # Reset sampling for Sobol and Random for Uniform
        return self.rand(n, d, 0)

    def reset_sample(self, n, d):
        self.reset()
        return self.rand(n, d, self.counter)


def freq_boundary(central_freq, w20):
    rest_freq = 1.420e9
    c = 3e5
    bw = rest_freq * w20 / c
    upper_freq = central_freq - bw / 2
    lower_freq = central_freq + bw / 2
    return lower_freq, upper_freq


def inside_box(points, min_values, max_values):
    dim = len(points)
    for i in range(dim):
        less_min = np.where(points[i] < min_values[i])[0]
        if less_min.shape[0] > 0:
            total_length = points[i][0, 1] - points[i][0, 0]
            for j in less_min:
                points[i][j, 0] = min_values[i]
                points[i][j, 1] = min_values[i] + total_length

        greater_max = np.where(points[i] >= max_values[i])[0]
        if greater_max.shape[0] > 0:
            total_length = points[i][0, 1] - points[i][0, 0]
            for j in greater_max:
                points[i][j, 0] = max_values[i] - total_length - 1
                points[i][j, 1] = max_values[i] - 1
    return points


def random_center_box(rdn, total_length, center_point, precuation, min_values, max_values):
    n_points = rdn.shape[0]
    dim = rdn.shape[1]
    radius = int(total_length / 2) - precuation
    coord = [np.zeros((n_points, 2), dtype=np.int) for _ in range(dim)]
    for i in range(dim):
        coord[i][:, 0] = (rdn[:, i] * 2 * radius + center_point[i] - int(total_length / 2) - radius).astype(np.int)
        coord[i][:, 1] = coord[i][:, 0] + total_length
    return inside_box(coord, min_values, max_values)


def random_in_interval(rdn, interval, length):
    n_points = rdn.shape[0]
    dim = rdn.shape[1]
    coord = [np.zeros((n_points, 2), dtype=np.int) for _ in range(dim)]
    for i in range(dim):
        coord[i][:, 0] = rdn[:, i] * max((interval[i, 1] - interval[i, 0] - length), 0) + interval[i, 0] + length/2
        coord[i][:, 1] = coord[i][:, 0] + length
    return coord
