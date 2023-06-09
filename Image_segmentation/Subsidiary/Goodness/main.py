from argparse import ArgumentParser
import run
import numpy as np
def tuple_type(strings):
    strings = strings.replace("(", "").replace(")", "")
    mapped_int = map(int, strings.split(","))
    return tuple(mapped_int)

def main(args):
  if (args.classid)[0]==1000:
    args.classid = list(np.linspace(1,40,40).astype('int32'))
    #print(args.classid )
    if args.input_imagesize==0:
        args.input_imagesize=args.imagesize
  
  run.start(args)
  return args 

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--channel_input', type=int ,default=3, required=False)
    parser.add_argument('--mode', type=str ,default='only_vis', required=False)
    parser.add_argument('--task', type=str ,default='semantic', required=False)
    parser.add_argument('--data', type=str ,default='train', required=False)
    parser.add_argument('--network', type=str ,default='inception_default', required=False)
    parser.add_argument('--score', type=str ,default='optical', required=False)
    parser.add_argument('--score_path', type=str ,default='train_optical', required=False)
    parser.add_argument('--jsonpath', type=str ,default='/content/', required=False)
    parser.add_argument('--model_dir', type=str , required=False)
    parser.add_argument('--basepath', type=str , default='/content/', required=False)
    parser.add_argument('--imagesize', type=tuple_type, required=True)
    parser.add_argument('--colorspace', type=str ,default='rgb', required=False)
    parser.add_argument('--classid', type=list, default=[1000] , required=False)
    parser.add_argument('--tr1', type=float ,default=0.90, required=False)
    parser.add_argument('--tr2', type=float ,default=1, required=False)
    parser.add_argument('--clipscore', type=str ,default='result_FS_cliptrain_optical.csv', required=False)
    parser.add_argument('--allscore', type=str ,default='result_train_optical.csv', required=False)
    parser.add_argument('--batchsize', type=int ,default=32, required=False)
    parser.add_argument('--epoch', type=int ,default=30, required=False)
    parser.add_argument('--branch_input', type=int ,default=2, required=False)
    parser.add_argument('--input_imagesize',default=(0), type=tuple_type, required=False)
    parser.add_argument('--baseinput', type=str , default='/content/', required=False)
    parser.add_argument('--baseinput2', type=str , default='/content/', required=False)

    parser.add_argument('--config', type=int , default=0, required=False)
    parser.add_argument('--restore', type=bool , default=False, required=False)


    args = parser.parse_args()

    main(args)
