# Profiling Result Files

## Explanation of each file in the folder:

- profiling_result.json: a json file contains parameters, profiling stats and results.
- profiling_resources_usage.json: a json file contains resources usage. To best view it, use [perfetto](https://ui.perfetto.dev/).
    - the time unit is microseconds
- profiling_result_op.csv: a csv file contains profiling results of OP. It is ideal for identifying which OP costs much or post processing.
    - Data Wrangler supports df table script, for example, `df = df.groupby(['op_type', 'ep'], as_index=False)['avg_us'].sum()` will sum avg_us grouped by op_type and ep
- profiling_result_op.json: a json file contains profiling results of OP. It is optionally organized in hierarchy if names are in the format `/A/B/C`. To best view it, use [perfetto](https://ui.perfetto.dev/).
- log.txt: the logs during the profiling.
- onnxruntime_profile__xxx.json: a json file contains all onnxruntime results of OP. The raw data. See more in [profiling](https://onnxruntime.ai/docs/performance/tune-performance/profiling-tools.html).
- onnxruntime_qnn_profile.csv: a csv file contains all qnn results of OP. The raw data.

## Explanation of data columns / properties

- op_name: the name of OP node. Note that certain nodes could be merged together like Conv+Relu, so the name could be any of them.
- op_type: the type of OP type.
    * EP_ADDED_OP: the op is added during compilation and could not find in original model.
- results_us: results in microseconds.
- ep: the EP that the model or node is running on.
- ts: the number of microseconds that have elapsed since 1970-01-01T00:00:00.000Z.
