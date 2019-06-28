"""
Modified from Bootstrap class: 
#   bootstrap.py - resampling analysis for multiple comparisons
#   Copyright (C) 2011 Gian-Carlo Pascutto <gcp@sjeng.org>
"""
import numpy as np
from scipy.stats.distributions import  t


def medians(data):
    """Return the list of medians corresponding to the data passed
       in table form. For an even number of items, the median is
       defined as the element just before the halfway point."""
    return np.median(data, 1)


def diffmean(xl, yl):
    """Return the difference between the means of 2 lists."""
    return np.absolute(np.mean(xl) - np.mean(yl))


def confInt(data, alpha=0.05):
    n = data.shape[1]  # number of measurements
    dof = n - 1  # degrees of freedom
    std_x = np.std(data, 1)  # standard deviation of measurements
    pred_interval = t.ppf(1-alpha/2., dof)*std_x*np.sqrt(1.+1./n)
    return pred_interval


def welcht(xl, yl):
    """Welch t-test for independent samples. This is similar
    to the student t-test, except that it does not require
    equal variances. Returns the test statistic."""
    # Denominator in the Welch's t statistic. This is a
    # variance estimate based on the available sample.
    # See also: Behrens-Fisher problem."""
    denom = (np.var(xl)/xl.shape[0] + np.var(yl)/yl.shape[0])**0.5
    # Avoid division by zero if both lists are identical
    denom = denom + 1e-35
    return diffmean(xl, yl)/denom


def student_paired(xl, yl):
    """Student t-test for paired samples. Arguments are two lists of
    measurements. Returns the test statistic."""
    diffs = [x - y for x, y in zip(xl, yl)]
    meandiff = abs(sum(diffs)/len(diffs))
    ssd = np.var(diffs)**0.5
    # Avoid division by zero if both lists are identical
    ssd = ssd + 1e-35
    return meandiff/(ssd*(len(diffs)**0.5))


def wilcoxon(xl, yl):
    """Performs a Wilcoxon signed-rank test for paired samples,
       with adjustments for handling zeroes due to Pratt. 
       The test statistic is inverted compared to a normal Wilcoxon 
       signed-rank test and cannot be interpreted directly."""
    diffs = [x - y for x, y in zip(xl, yl) if x != y]
    abs_diff = [abs(x) for x in diffs]
    abs_diff_rank = sorted((diff, idx) for idx, diff in enumerate(abs_diff))
    w_plus = 0
    w_minus = 0
    uniqrank = {}
    # ties at 0 increment the start rank (Pratt, 1959)
    startrank = len(xl) - len(diffs)
    for rank, (diff, idx) in enumerate(abs_diff_rank):
        if diff in uniqrank:
            rank = uniqrank[diff]
        else:
            # (start + (start + ties - 1)) / 2
            ties = abs_diff.count(diff)
            rank = (2 * (rank + 1) + (ties - 1)) / 2.0
            uniqrank[diff] = rank
        if diffs[idx] > 0:
            w_plus += startrank + rank
        else:
            w_minus += startrank + rank
    # invert by making high values more significant,
    # simplifies rest of code
    return 1.0/(1.0+min(w_plus, w_minus))


def mann_whitney(xl, yl):
    """Mann-Whitney-Wilcoxon U test for independent samples. This is
    the nonparametric alternative to the student t-test."""
    # make a merged list of all values, and sort it, but remember
    # from which sample each value came
    ranked = sorted([(x, 0) for x in xl] + [(y, 1) for y in yl])
    x_ranksum = 0
    uniqrank = {}
    for rank, (value, series) in enumerate(ranked):
        if value in uniqrank:
            rank = uniqrank[value]
        else:
            ties = ranked.count((value, 0)) + ranked.count((value, 1))
            rank = (2 * (rank + 1) + (ties - 1)) / 2.0
            uniqrank[value] = rank
        if series == 0:
            x_ranksum += rank
    u_1 = x_ranksum - ((len(xl)*(len(xl)+1))/2)
    u_2 = (len(xl)*len(yl)) - u_1
    # invert to make higher more significant
    return 1.0/(1.0+min(u_1, u_2))


def options(opt):
    func = 'undefined'
    if opt == 'welcht':
        func = welcht
    elif opt == 'student_paired':
        func = student_paired
    elif opt == 'wilcoxon':
        func = wilcoxon
    elif opt == 'mann_whitney':
        func = mann_whitney
    elif opt == 'bootstrap':
        func = bootstrap
    elif opt == 'permute':
        func = permute
    return func


def get_stats(func, data, ctrl):
    """Apply the test statistic passed as 'func' to the 'data' for
       the pairs to compare in 'compars'."""
       
    return [options(func)(data[x, :ctrl], data[x, ctrl:]) for x in range(data.shape[0])]


def permute(data):
    """Perform a resampling WITHOUT replacement to the table in 'data'.
       resamplings only happen within rows. Returns a masked array"""

    samp=[np.random.permutation(row) for row in data]
    return np.ma.masked_array(samp,np.isnan(samp))


def bootstrap(data):
    """Perform a resampling WITH replacement to the table in 'data'.
    resamplings only happen within rows. Returns a masked array"""
    samp = [[row[np.random.randint(data.shape[1])] for _ in row] for row in data]
    return np.ma.masked_array(samp,np.isnan(samp))


def pdiff(tstat, ptstat):
    if tstat >= ptstat:
        return 0
    else:
        return 1


def resample_pvals(data1, data2, teststat='welcht', resample_func='permute', permutes=1000):
    """Given a set of data and a test statistic in options.teststat,
       calculate the probability that the test statistic is as extreme
       as it is due to random chance, for the comparisons in 'compars'.
       The probability is calculated by a re-randomization permutation.
       Summary:
       calculate original test stat
        phits= 0 for each comparison
        resample, get stats again
        phits = +1 if original stat lower than permuted stat
        return phit/permutations
        = probability of Ha
       """
    if data1.shape[0] != data2.shape[0]:
        raise(LookupError('Datasets must have equal first dimension. '
            'Data1: %s, Data2: %s' % (data1.shape[0], data2.shape[0])))
    data = np.concatenate( (data1, data2), 1)
    ctrl = data1.shape[1]
    tstat = get_stats(teststat, data, ctrl)
    phits = [0 for _ in range(data.shape[0])]
    
    for _ in range(permutes):
        pdata = options(resample_func)(data)
        pteststat = get_stats(teststat, pdata, ctrl)
        phits = [phits[z] + pdiff(tstat[z], pteststat[z])
                 for z in range(data.shape[0])]

    return [phit/float(permutes) for phit in phits]


def stepdown_adjust(data1, data2, teststat='welcht', resample_func='permute', permutes=1000):
    """Calculate a set of p-values for 'data', and adjust them for the 
    multiple comparisons in 'compars' being performed. The used algorithm 
    is a resampling based free step-down using the max-T algorithm 
    from Westfall & Young."""
    if data1.shape[0] != data2.shape[0]:
        raise(LookupError('Datasets must have equal first dimension. '
            'Data1: %s, Data2: %s' % (data1.shape[0], data2.shape[0])))
    data = np.concatenate( (data1, data2), 1)
    ctrl = data1.shape[1]
    tstat = get_stats(teststat, data, ctrl)
    # sort the test statistics, but remember which comparison they came from
    tstat_help = [(tval, idx) for idx, tval in enumerate(tstat)]
    sortedt = sorted(tstat_help)
    phits = [0 for _ in range(data.shape[0])]

    for _ in range(permutes):
        bdata = options(resample_func)(data) 
        btstat = get_stats(teststat, bdata, ctrl)

        # free step-down using maxT
        maxt = -1
        for torg, idx in sortedt:
            if (np.isnan(torg)):
                phits[idx] = phits[idx] + 1
            else:
                maxt = max(btstat[idx], maxt)
                if (maxt >= torg):
                    phits[idx] = phits[idx] + 1

    # the new p-value is the ratio with which such an extremal
    # statistic was observed in the resampled data
    new_pval = [phit/float(permutes) for phit in phits]

    # ensure monotonicity of p-values
    maxp = 0.0
    for _, idx in reversed(sortedt):
        maxp = max(maxp, new_pval[idx])
        new_pval[idx] = maxp

    return new_pval
