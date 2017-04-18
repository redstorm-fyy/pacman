import tensorflow as tf
import numpy as np
from tensorflow.python.client import timeline

class BonePosition:
    def __del__(self):
        self.sess.close()

    def calclocation(self):#->[vertexNum,matx]
        pose = tf.gather(self.pose, self.index,name="gather_pose")  # [boneNum,matx,maty],[vertexNum,vbnum]->[vertexNum,vbnum,matx,maty]
        bone = tf.gather(self.boneVar, self.index,name="gather_bone") # [boneNum,matx,maty],[vertexNum,vbnum]->[vertexNum,vbnum,matx,maty]
        cat=tf.constant(1.0,dtype=tf.float32,shape=[self.vertexNum,1])
        vertex=tf.concat([self.vertex,cat],axis=1,name="concat_vertex") #[vertexNum,matx+1],makesure maty=matx+1
        cat=tf.reshape(cat,[self.vertexNum,1,1])
        cat=tf.tile(cat,[1,self.vbnum,1],name="tile_cat") #[vertexNum,vbnum,1]

        vertex=tf.reshape(vertex,[self.vertexNum,self.maty,1])
        pose=tf.reshape(pose,[self.vertexNum,self.vbnum*self.matx,self.maty])
        location=tf.matmul(pose,vertex,name="matmul_pose") #[vertexNum,vbnum*matx,1]
        location=tf.reshape(location,[self.vertexNum,self.vbnum,self.matx])

        location=tf.concat([location,cat],axis=2,name="concat_location") #[vertexNum,vbnum,matx+1]
        location=tf.reshape(location,[self.vertexNum,self.vbnum,self.maty,1])
        location=tf.matmul(bone,location,name="matmul_bone") #[vertexNum,vbnum,matx,1]
        location=tf.reshape(location,[self.vertexNum,self.vbnum,self.matx])

        weight=tf.reshape(self.weight,[self.vertexNum,self.vbnum,1])
        location=tf.multiply(location,weight,name="multiply_weight") #[vertexNum,vbnum,matx]
        location=tf.reduce_sum(location,axis=[1],name="sum_weight")#[vertexNum,matx]
        return location

    def calcloss(self,location): #[vertexNum,matx],[featureNum,matx]->[]
        ab=tf.matmul(location,tf.transpose(self.feature),name="matmul_loss") #[vertexNum,featureNum]
        a=tf.reduce_sum(location*location,axis=1,name="sum_location") #[vertexNum]
        b=tf.reduce_sum(self.feature*self.feature,axis=1,name="sum_feature") #[featureNum]
        a=tf.reshape(a,[self.vertexNum,1])
        b=tf.reshape(b,[1,self.featureNum])
        loss=a-2*ab+b #[vertexNum,featureNum],Distance(A,B)=(A-B)(A-B)=AA-2AB+BB
        loss=tf.reduce_sum(tf.reduce_min(loss,axis=0,name="min_distance"),name="sum_loss")
        return loss

    def __init__(self,featureNum,boneNum,vertexNum,logdir=None,profile=None):
        self.speed=0.0001
        self.trainNum=200
        self.matx=3
        self.maty=self.matx+1
        self.vbnum=4 #one vertex connects vbnum bones
        self.featureNum=featureNum
        self.boneNum=boneNum
        self.vertexNum=vertexNum
        self.feature=tf.placeholder(tf.float32,shape=[self.featureNum,self.matx])
        self.bone=tf.placeholder(tf.float32,shape=[self.boneNum,self.matx,self.maty])
        self.boneVar=tf.Variable(tf.constant(0.0,dtype=tf.float32,shape=[self.boneNum,self.matx,self.maty]))
        self.boneInit=tf.assign(self.boneVar,self.bone)
        self.pose=tf.placeholder(tf.float32,shape=[self.boneNum,self.matx,self.maty])
        self.vertex=tf.placeholder(tf.float32,shape=[self.vertexNum,self.matx])
        self.weight=tf.placeholder(tf.float32,shape=[self.vertexNum,self.vbnum])
        self.index=tf.placeholder(tf.int32,shape=[self.vertexNum,self.vbnum])

        self.loc=self.calclocation()#[vertexNum,matx]
        self.loss=self.calcloss(self.loc)
        self.opt=tf.train.RMSPropOptimizer(self.speed).minimize(self.loss)
        tf.summary.scalar("loss", self.loss)

        self.sess=tf.Session()
        self.logdir=logdir
        if self.logdir is not None:
            self.writer=tf.summary.FileWriter(self.logdir,self.sess.graph)
            self.summary=tf.summary.merge_all()
        self.profile=profile

    def writeprofile(self,metadata):
        if self.profile is None:
            return
        tl=timeline.Timeline(metadata.step_stats)
        #ctf=tl.generate_chrome_trace_format(show_dataflow=True,show_memory=True)
        ctf = tl.generate_chrome_trace_format()
        with open(self.profile,"w") as f:
            f.write(ctf)

    def train(self,feed_dict):
        options=None
        metadata=None
        if self.profile is not None:
            options=tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
            metadata=tf.RunMetadata()
            self.trainNum=1
        self.sess.run([tf.global_variables_initializer(),self.boneInit],feed_dict={self.bone:feed_dict[self.bone]},options=options,run_metadata=metadata)
        for i in range(0,self.trainNum):
            self.sess.run(self.opt,feed_dict=feed_dict,options=options,run_metadata=metadata)
            self.writeprofile(metadata)
            if self.logdir is not None:
                summary=self.sess.run(self.summary,feed_dict=feed_dict,options=options,run_metadata=metadata)
                self.writer.add_summary(summary,i+1)
        bone=self.sess.run(self.boneVar,options=options,run_metadata=metadata)
        return bone

def ReadMatrixlist(f):
    mlist=[]
    lines=f.readlines()
    for s in lines:
        numArray=s.split(b"\t")
        mat=np.zeros([3,4],dtype=np.float32)
        for i in range(0,3):
            for j in range(0,4):
                mat[i][j]=numArray[i*4+j]
        mlist.append(mat)
    return mlist

def ReadVectorlist(f):
    vlist = []
    lines = f.readlines()
    for s in lines:
        numArray = s.split(b"\t")
        vec = np.zeros([3], dtype=np.float32)
        for i in range(0, 3):
            vec[i] = numArray[i]
        vlist.append(vec)
    return vlist

def ReadBone():
    with open("../graph/bones.txt","rb") as f:
        return ReadMatrixlist(f)
def ReadPose():
    with open("../graph/bindpose.txt","rb") as f:
        return ReadMatrixlist(f)

def ReadVertex():
    with open("../graph/vertices.txt","rb") as f:
        return ReadVectorlist(f)
def ReadFeature():
    with open("../graph/new_vertices.txt","rb") as f:
        return ReadVectorlist(f)

def ReadIndexAndWeight():
    with open("../graph/weights.txt","rb") as f:
        ilist=[]
        wlist=[]
        lines=f.readlines()
        for s in lines:
            numArray=s.split(b"\t")
            index=np.zeros([4],dtype=np.int32)
            weight=np.zeros([4],dtype=np.float32)
            for i in range(0,4):
                index[i]=numArray[i*2]
                weight[i]=numArray[i*2+1]
            ilist.append(index)
            wlist.append(weight)
        return ilist,wlist

def WriteNewBone(bone):
    with open("../graph/new_bone.txt","wb") as f:
        for b in bone:
            b=np.array(b)
            b.tofile(f,sep="\t")
            f.write(b"\r\n")

bone=ReadBone()
pose=ReadPose()
vertex=ReadVertex()
index,weight=ReadIndexAndWeight()
feature=ReadFeature()

featureNum=len(feature)
boneNum=len(bone)
poseNum=len(pose)
vertexNum=len(vertex)
indexNum=len(index)
weightNum=len(weight)

print(featureNum,boneNum,poseNum,vertexNum,indexNum,weightNum)

bp=BonePosition(featureNum,boneNum,vertexNum,None,"../timeline.json")
#bp=BonePosition(featureNum,boneNum,vertexNum,"../logs")
#bp=BonePosition(featureNum,boneNum,vertexNum)

feed_dict={bp.feature:feature,
           bp.bone:bone,
           bp.pose:pose,
           bp.vertex:vertex,
           bp.weight:weight,
           bp.index:index}

print("begin training")
bone=bp.train(feed_dict)
WriteNewBone(bone)
